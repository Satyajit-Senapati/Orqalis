import hashlib
import math
import re
from collections.abc import Callable
from uuid import UUID, uuid5

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.domain.errors import (
    ConflictError,
    EmbeddingUnavailableError,
    InputError,
    NotFoundError,
)
from orqalis.domain.memory import (
    ArchitectureEntity,
    ArchitectureRelation,
    ContextPack,
    MemoryHealth,
    MemoryItem,
    MemoryMatch,
    MemoryRefresh,
    MemorySource,
    MemoryType,
    ProjectSnapshot,
    RepositoryFile,
)
from orqalis.domain.project import Project
from orqalis.git.contracts import GitService
from orqalis.graph import ProjectGraphEngine
from orqalis.memory.indexing import DeterministicMemoryIndexer
from orqalis.memory.ports import EmbeddingProvider, MemoryIndexer, MemoryRepository
from orqalis.observability.instrumentation import observed


class MemoryService:
    def __init__(
        self,
        unit_of_work: Callable[[], ProjectUnitOfWork],
        git: GitService,
        indexer: MemoryIndexer | None = None,
        embeddings: EmbeddingProvider | None = None,
    ) -> None:
        self.unit_of_work = unit_of_work
        self.git = git
        self.indexer = indexer or DeterministicMemoryIndexer()
        self.embeddings = embeddings

    def _embed(self, text: str) -> tuple[float, ...] | None:
        if self.embeddings is None:
            return None
        try:
            result = self.embeddings.embed(text)
        except EmbeddingUnavailableError:
            return None
        if (
            len(result) != self.embeddings.dimensions
            or not result
            or not all(math.isfinite(value) for value in result)
            or not any(result)
        ):
            raise InputError("Embedding provider returned an invalid vector")
        return result

    def _backfill_embeddings(self, repository: MemoryRepository, project_id: UUID) -> bool:
        if self.embeddings is None:
            return False
        changed = False
        while items := repository.missing_embeddings(project_id, self.embeddings.model_id):
            for item in items:
                embedding = self._embed(item.content)
                if embedding is None:
                    return changed  # Preserve offline fallback without retrying every stored item.
                repository.save_embedding(project_id, item.id, embedding, self.embeddings.model_id)
                changed = True
        return changed

    def _fingerprint(self, project_id: UUID, commit: str) -> str:
        embedding = (
            f"{self.embeddings.model_id}:{self.embeddings.dimensions}"
            if self.embeddings
            else "structured"
        )
        identity = f"{project_id}:{commit}:indexer={self.indexer.VERSION}:embedding={embedding}"
        return hashlib.sha256(identity.encode()).hexdigest()

    @observed("memory.refresh")
    def refresh(self, project: Project, origin_run: UUID | None = None) -> MemoryRefresh:
        with self.unit_of_work() as uow:
            repository = uow.memory
            repository.lock_project(project.id)
            head = self.git.resolve_commit(project.repo_root, "HEAD")
            previous = repository.latest_snapshot(project.id)
            changed_indexer = bool(
                previous
                and previous.repo_fingerprint
                != self._fingerprint(project.id, previous.indexed_commit_sha)
            )
            backfilled = bool(
                previous
                and not changed_indexer
                and self._backfill_embeddings(repository, project.id)
            )
            if previous and previous.indexed_commit_sha == head and not changed_indexer:
                if backfilled:
                    uow.commit()
                return MemoryRefresh(snapshot=previous, reused=True)
            rebuild = bool(
                previous
                and (
                    changed_indexer
                    or not self.git.has_commit(project.repo_root, previous.indexed_commit_sha)
                )
            )
            if previous and not rebuild:
                paths = self.git.changed_files(project.repo_root, previous.indexed_commit_sha, head)
            elif previous:
                paths = tuple(
                    sorted(
                        set(self.git.tracked_files(project.repo_root, head)).union(
                            file.path for file in repository.files(project.id)
                        )
                    )
                )
            else:
                paths = self.git.tracked_files(project.repo_root, head)
            scanned = []
            invalidations = 0
            for path in paths:
                if not self.indexer.allows(path):
                    invalidations += repository.invalidate_path(project.id, path, None)
                    repository.remove_file(project.id, path)
                    continue
                content = self.git.read_file_if_present(
                    project.repo_root, head, path, self.indexer.MAX_BYTES
                )
                scanned.append(path)
                indexed = self.indexer.index(path, content) if content is not None else None
                if indexed is None:
                    invalidations += repository.invalidate_path(project.id, path, None)
                    repository.remove_file(project.id, path)
                    continue
                old = repository.current_file(project.id, path)
                if old and old.content_hash == indexed.content_hash and not rebuild:
                    continue
                item = MemoryItem(
                    project_id=project.id,
                    type=indexed.memory_type,
                    title=path,
                    content=indexed.summary,
                    source_commit=head,
                    introduced_by_run=origin_run,
                )
                source = MemorySource(
                    memory_item_id=item.id,
                    source_ref=path,
                    content_hash=indexed.content_hash,
                    commit_sha=head,
                )
                repository.add_item(
                    item,
                    source,
                    self._embed(item.content),
                    self.embeddings.model_id if self.embeddings else None,
                )
                invalidations += repository.invalidate_path(project.id, path, item.id)
                repository.save_file(
                    RepositoryFile(
                        id=old.id if old else uuid5(project.id, path),
                        project_id=project.id,
                        path=path,
                        language=indexed.language,
                        role=indexed.role,
                        content_hash=indexed.content_hash,
                        last_seen_commit=head,
                    )
                )
            files = repository.files(project.id)
            languages = sorted({file.language for file in files if file.language})
            summary = MemoryItem(
                project_id=project.id,
                type=MemoryType.ARCHITECTURE,
                title="Project overview",
                content=f"Project {project.name}: {len(files)} indexed files. "
                f"Languages: {', '.join(languages)}. "
                f"Test files: {sum(file.role == 'test' for file in files)}.",
                source_commit=head,
                introduced_by_run=origin_run,
            )
            repository.add_item(
                summary,
                MemorySource(
                    memory_item_id=summary.id,
                    source_type="git_tree",
                    source_ref=".",
                    content_hash=hashlib.sha256(head.encode()).hexdigest(),
                    commit_sha=head,
                ),
                self._embed(summary.content),
                self.embeddings.model_id if self.embeddings else None,
            )
            invalidations += repository.invalidate_path(project.id, ".", summary.id)
            if self.git.resolve_commit(project.repo_root, "HEAD") != head:
                raise ConflictError("HEAD changed while memory was refreshing; retry")
            snapshot = ProjectSnapshot(
                project_id=project.id,
                indexed_commit_sha=head,
                repo_fingerprint=self._fingerprint(project.id, head),
                files_scanned=len(scanned),
                invalidations=invalidations,
            )
            repository.save_snapshot(snapshot)
            uow.commit()
            return MemoryRefresh(
                snapshot=snapshot, scanned_paths=tuple(scanned), invalidated_items=invalidations
            )

    def health(self, project: Project) -> MemoryHealth:
        status = self.git.status(project.repo_root)
        dirty_paths = tuple(
            path
            for path in status.changed_paths
            if path != ".orqalis" and not path.startswith(".orqalis/")
        )
        with self.unit_of_work() as uow:
            snapshot = uow.memory.latest_snapshot(project.id)
            indexed = snapshot.indexed_commit_sha if snapshot else None
            return MemoryHealth(
                project_id=project.id,
                indexed_commit=indexed,
                current_commit=status.head,
                fresh=bool(
                    snapshot
                    and indexed == status.head
                    and snapshot.repo_fingerprint == self._fingerprint(project.id, status.head)
                    and not dirty_paths
                ),
                dirty_paths=dirty_paths,
                active_items=uow.memory.active_count(project.id),
            )

    def search(self, project: Project, query: str, limit: int = 10) -> tuple[MemoryMatch, ...]:
        if not 1 <= limit <= 100 or len(query) > 10_000:
            raise InputError("Search limit must be 1..100 and query at most 10000 characters")
        self.refresh(project)
        terms = tuple(dict.fromkeys(re.findall(r"[a-z0-9_]{2,}", query.lower())))[:32]
        head = self.git.resolve_commit(project.repo_root, "HEAD")
        embedding = self._embed(query)
        model = self.embeddings.model_id if self.embeddings else None
        ancestry: dict[str, bool] = {}
        excluded: set[UUID] = set()
        with self.unit_of_work() as uow:
            while True:
                matches = uow.memory.search(
                    project.id, terms, limit, embedding, model, tuple(sorted(excluded))
                )
                rejected = set()
                for match in matches:
                    if match.item.type != MemoryType.PREVIOUS_RUN:
                        continue
                    commit = match.item.source_commit
                    if commit not in ancestry:
                        ancestry[commit] = self.git.is_ancestor(project.repo_root, commit, head)
                    if not ancestry[commit]:
                        rejected.add(match.item.id)
                if not rejected:
                    return matches
                # Exclude before ranking/limit and refill so unrelated history cannot
                # crowd current source facts out of a bounded Context Pack.
                excluded.update(rejected)

    @observed("memory.context")
    def context(self, project: Project, task: str, max_chars: int = 20_000) -> ContextPack:
        if not 1000 <= max_chars <= 200_000:
            raise InputError("Context budget must be between 1000 and 200000 characters")
        from orqalis.context.agent import agent_context
        from orqalis.context.builder import ProjectContextBuilder

        with self.unit_of_work() as uow:
            canonical_project = uow.projects.get(project.id)
        if canonical_project is None:
            raise NotFoundError("Project not found")
        project_pack = ProjectContextBuilder(
            canonical_project.repo_root,
            source_root=project.repo_root,
            git=self.git,
        ).build(task, max_chars)
        return agent_context(canonical_project, project_pack)

    def graph(
        self, project: Project
    ) -> tuple[tuple[ArchitectureEntity, ...], tuple[ArchitectureRelation, ...]]:
        graph = ProjectGraphEngine(project.repo_root, git=self.git).refresh().graph
        identifiers = {
            node.id: uuid5(project.id, f"project-graph-node:{node.id}") for node in graph.nodes
        }
        paths = {node.id: node.file_path for node in graph.nodes}
        entities = tuple(
            ArchitectureEntity(
                id=identifiers[node.id],
                project_id=project.id,
                entity_type=str(node.kind).casefold(),
                name=node.name,
                source_refs=(node.file_path,) if node.file_path else (),
            )
            for node in graph.nodes
        )
        relations = tuple(
            ArchitectureRelation(
                id=uuid5(project.id, f"project-graph-edge:{edge.id}"),
                project_id=project.id,
                source_entity_id=identifiers[edge.source_id],
                relation_type=str(edge.relation).casefold(),
                target_entity_id=identifiers[edge.target_id],
                confidence=edge.confidence,
                source_refs=tuple(
                    dict.fromkeys(
                        path
                        for path in (paths.get(edge.source_id), paths.get(edge.target_id))
                        if path
                    )
                ),
            )
            for edge in graph.edges
            if edge.source_id in identifiers and edge.target_id in identifiers
        )
        return entities, relations
