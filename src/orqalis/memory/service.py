import hashlib
import math
import re
from collections.abc import Callable
from pathlib import PurePosixPath
from uuid import UUID, uuid5

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.domain.errors import ConflictError, EmbeddingUnavailableError, InputError
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

    @observed("memory.refresh")
    def refresh(self, project: Project, origin_run: UUID | None = None) -> MemoryRefresh:
        with self.unit_of_work() as uow:
            repository = uow.memory
            repository.lock_project(project.id)
            head = self.git.resolve_commit(project.repo_root, "HEAD")
            previous = repository.latest_snapshot(project.id)
            if previous and previous.indexed_commit_sha == head:
                return MemoryRefresh(snapshot=previous, reused=True)
            paths = (
                self.git.changed_files(project.repo_root, previous.indexed_commit_sha, head)
                if previous
                else self.git.tracked_files(project.repo_root, head)
            )
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
                if old and old.content_hash == indexed.content_hash:
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
                self._index_graph(repository, project.id, path)
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
                repo_fingerprint=hashlib.sha256(f"{project.id}:{head}".encode()).hexdigest(),
                files_scanned=len(scanned),
                invalidations=invalidations,
            )
            repository.save_snapshot(snapshot)
            uow.commit()
            return MemoryRefresh(
                snapshot=snapshot, scanned_paths=tuple(scanned), invalidated_items=invalidations
            )

    def _index_graph(self, repository: MemoryRepository, project_id: UUID, path: str) -> None:
        module = f"directory:{PurePosixPath(path).parent}"
        file_id, module_id = uuid5(project_id, path), uuid5(project_id, module)
        repository.save_entity(
            ArchitectureEntity(id=file_id, project_id=project_id, name=path, source_refs=(path,))
        )
        repository.save_entity(
            ArchitectureEntity(
                id=module_id,
                project_id=project_id,
                entity_type="directory",
                name=module,
                source_refs=(),
            )
        )
        repository.save_relation(
            ArchitectureRelation(
                id=uuid5(project_id, f"{path}:belongs_to:{module}"),
                project_id=project_id,
                source_entity_id=file_id,
                relation_type="belongs_to",
                target_entity_id=module_id,
                source_refs=(path,),
            )
        )

    def health(self, project: Project) -> MemoryHealth:
        status = self.git.status(project.repo_root)
        with self.unit_of_work() as uow:
            snapshot = uow.memory.latest_snapshot(project.id)
            indexed = snapshot.indexed_commit_sha if snapshot else None
            return MemoryHealth(
                project_id=project.id,
                indexed_commit=indexed,
                current_commit=status.head,
                fresh=indexed == status.head and not status.changed_paths,
                dirty_paths=status.changed_paths,
                active_items=uow.memory.active_count(project.id),
            )

    def search(self, project: Project, query: str, limit: int = 10) -> tuple[MemoryMatch, ...]:
        if not 1 <= limit <= 100 or len(query) > 10_000:
            raise InputError("Search limit must be 1..100 and query at most 10000 characters")
        self.refresh(project)
        terms = tuple(dict.fromkeys(re.findall(r"[a-z0-9_]{2,}", query.lower())))[:32]
        with self.unit_of_work() as uow:
            return uow.memory.search(
                project.id,
                terms,
                limit,
                self._embed(query),
                self.embeddings.model_id if self.embeddings else None,
            )

    @observed("memory.context")
    def context(self, project: Project, task: str, max_chars: int = 20_000) -> ContextPack:
        if not 1000 <= max_chars <= 200_000:
            raise InputError("Context budget must be between 1000 and 200000 characters")
        matches = self.search(project, task, limit=30)
        health = self.health(project)
        selected = []
        size = 0
        for match in matches:
            item_size = len(match.model_dump_json())
            if size + item_size <= max_chars:
                selected.append(match)
                size += item_size
        paths = tuple(
            sorted(
                {
                    source.source_ref
                    for match in selected
                    for source in match.sources
                    if source.source_type == "file"
                }
            )
        )
        targeted = tuple(sorted(set(paths).intersection(health.dirty_paths)))
        confidence = max((match.score * match.item.confidence for match in selected), default=0)
        if not health.fresh:
            confidence = min(confidence, 0.5)
            targeted = tuple(sorted(set(targeted).union(health.dirty_paths)))
        return ContextPack(
            project_id=project.id,
            task=task,
            items=tuple(selected),
            relevant_files=paths,
            freshness=health,
            confidence=confidence,
            targeted_inspection_paths=targeted,
            requires_inspection=confidence < 0.7 or not health.fresh,
            size_chars=size,
        )

    def graph(
        self, project: Project
    ) -> tuple[tuple[ArchitectureEntity, ...], tuple[ArchitectureRelation, ...]]:
        with self.unit_of_work() as uow:
            return uow.memory.graph(project.id)
