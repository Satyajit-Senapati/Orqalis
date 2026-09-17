"""Project-root-bound generation and lexical retrieval for derived indexes."""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path

from pydantic import ValidationError

from orqalis.domain.errors import ConflictError, InputError, PolicyDeniedError
from orqalis.git.service import LocalGitService
from orqalis.graph import GraphNode, GraphNodeKind, ProjectGraphEngine
from orqalis.indexing.models import (
    INDEX_SCHEMA_VERSION,
    INDEX_VERSION,
    IndexArtifact,
    IndexBuildMetrics,
    IndexDocument,
    IndexedTask,
    IndexManifest,
    IndexRecordKind,
    IndexTerms,
    ProjectIndexBuildResult,
    ProjectIndexMatch,
)
from orqalis.memory.curated import CuratedMemoryStore, DurableMemoryRecord
from orqalis.persistence.filesystem import (
    FileLock,
    FilesystemFormatError,
    ProjectLayout,
    TaskCapsuleStore,
    atomic_write_bytes,
    ensure_no_filesystem_links,
    load_manifest,
    read_json_object,
)
from orqalis.security.redaction import safe_diagnostic

_TERM = re.compile(r"[a-z0-9_]{2,}")
_ARTIFACTS = (
    "files.jsonl",
    "symbols.jsonl",
    "relations.jsonl",
    "terms.json",
    "task-index.json",
)
_MAX_SUMMARY_CHARS = 16_000


class ProjectIndex:
    """Build and query a disposable index for exactly one initialized repository."""

    def __init__(self, root: Path, *, git: LocalGitService | None = None) -> None:
        self.git = git or LocalGitService()
        self.root = self.git.root(root)
        self.layout = ProjectLayout(self.root)
        self.index_dir = self._storage_target(self.layout.index)
        self.manifest_path = self._storage_target(self.index_dir / "manifest.json")
        self.project_manifest = load_manifest(self.layout)
        self.graph = ProjectGraphEngine(self.root, git=self.git)
        self.memory = CuratedMemoryStore(self.layout)
        self.tasks = TaskCapsuleStore(self.layout)

    def rebuild(self) -> ProjectIndexBuildResult:
        """Regenerate every index artifact from canonical project-local sources."""

        started = time.perf_counter()
        with FileLock(self.layout.lock("project-index")):
            graph_result = self.graph.rebuild()
            memory_records = self.memory.list()
            tasks = self._task_records()
            file_nodes = tuple(
                node for node in graph_result.graph.nodes if node.kind == GraphNodeKind.FILE
            )
            symbol_nodes = tuple(
                node for node in graph_result.graph.nodes if node.kind != GraphNodeKind.FILE
            )
            documents = self._documents(file_nodes, symbol_nodes, memory_records, tasks)
            terms = self._terms(documents)

            files_payload = _jsonl_bytes(
                {
                    "schema_version": INDEX_SCHEMA_VERSION,
                    "index_version": INDEX_VERSION,
                    **node.model_dump(mode="json"),
                }
                for node in file_nodes
            )
            symbols_payload = _jsonl_bytes(
                {
                    "schema_version": INDEX_SCHEMA_VERSION,
                    "index_version": INDEX_VERSION,
                    **node.model_dump(mode="json"),
                }
                for node in symbol_nodes
            )
            relations_payload = _jsonl_bytes(
                {
                    "schema_version": INDEX_SCHEMA_VERSION,
                    "index_version": INDEX_VERSION,
                    **edge.model_dump(mode="json"),
                }
                for edge in graph_result.graph.edges
            )
            terms_payload = _json_bytes(terms.model_dump(mode="json"))
            task_payload = _json_bytes(
                {
                    "schema_version": INDEX_SCHEMA_VERSION,
                    "index_version": INDEX_VERSION,
                    "tasks": [task.model_dump(mode="json") for task in tasks],
                }
            )
            payloads = {
                "files.jsonl": files_payload,
                "symbols.jsonl": symbols_payload,
                "relations.jsonl": relations_payload,
                "terms.json": terms_payload,
                "task-index.json": task_payload,
            }
            record_counts = {
                "files.jsonl": len(file_nodes),
                "symbols.jsonl": len(symbol_nodes),
                "relations.jsonl": len(graph_result.graph.edges),
                "terms.json": len(documents),
                "task-index.json": len(tasks),
            }

            self.index_dir.mkdir(parents=True, exist_ok=True)
            for name in _ARTIFACTS:
                atomic_write_bytes(self._storage_target(self.index_dir / name), payloads[name])

            metrics = IndexBuildMetrics(
                duration_ms=_duration_ms(started),
                documents_indexed=len(documents),
                terms_indexed=len(terms.postings),
                file_records=len(file_nodes),
                symbol_records=len(symbol_nodes),
                relation_records=len(graph_result.graph.edges),
                memory_records=len(memory_records),
                task_records=len(tasks),
                graph_processed_files=graph_result.metrics.processed_files,
                graph_cache_hits=graph_result.metrics.cache_hits,
                graph_cache_misses=graph_result.metrics.cache_misses,
            )
            project_id, project_name = self._project_identity()
            manifest = IndexManifest(
                project_id=project_id,
                project_name=project_name,
                indexed_commit=graph_result.manifest.indexed_commit,
                indexed_branch=graph_result.manifest.indexed_branch,
                graph_schema_version=graph_result.manifest.schema_version,
                parser_version=graph_result.manifest.parser_version,
                artifacts={
                    name: IndexArtifact(
                        sha256=hashlib.sha256(payloads[name]).hexdigest(),
                        bytes=len(payloads[name]),
                        records=record_counts[name],
                    )
                    for name in _ARTIFACTS
                },
                metrics=metrics,
            )
            # The manifest is the commit marker and is therefore always written last.
            atomic_write_bytes(
                self.manifest_path,
                _json_bytes(manifest.model_dump(mode="json")),
            )
            return ProjectIndexBuildResult(manifest=manifest, metrics=metrics)

    def search(self, query: str, limit: int = 10) -> tuple[ProjectIndexMatch, ...]:
        """Search repository, memory, and task records using the local term index."""

        if not query.strip():
            raise InputError("Project index query must not be empty")
        if limit < 1 or limit > 100:
            raise InputError("Project index search limit must be between 1 and 100")
        query_terms = _tokenize(query)
        if not query_terms:
            raise InputError("Project index query must contain searchable terms")
        loaded = self._load()
        if loaded is None:
            self.rebuild()
            loaded = self._load()
        if loaded is None:
            raise ConflictError("Project index could not be rebuilt")
        _, terms = loaded

        matched: defaultdict[str, set[str]] = defaultdict(set)
        for term in query_terms:
            for document_id in terms.postings.get(term, ()):
                matched[document_id].add(term)
        ranked: list[ProjectIndexMatch] = []
        folded_query = query.casefold().strip()
        for document_id, found in matched.items():
            document = terms.documents.get(document_id)
            if document is None:
                continue
            title_terms = set(_tokenize(document.title))
            path_terms = set(_tokenize(document.path or ""))
            score = float(len(found) * 10)
            score += sum(3 for term in found if term in title_terms)
            score += sum(2 for term in found if term in path_terms)
            if folded_query in document.title.casefold():
                score += 5
            ranked.append(
                ProjectIndexMatch(
                    document=document,
                    score=score,
                    matched_terms=tuple(term for term in query_terms if term in found),
                )
            )
        ranked.sort(
            key=lambda item: (
                -item.score,
                item.document.title.casefold(),
                item.document.id,
            )
        )
        return tuple(ranked[:limit])

    def _load(self) -> tuple[IndexManifest, IndexTerms] | None:
        if not self.manifest_path.is_file():
            return None
        try:
            manifest = IndexManifest.model_validate(read_json_object(self.manifest_path))
            project_id, _ = self._project_identity()
            if (
                manifest.schema_version != INDEX_SCHEMA_VERSION
                or manifest.index_version != INDEX_VERSION
                or manifest.project_id != project_id
            ):
                return None
            for name in _ARTIFACTS:
                artifact = manifest.artifacts.get(name)
                path = self._storage_target(self.index_dir / name)
                if artifact is None or not path.is_file():
                    return None
                if hashlib.sha256(path.read_bytes()).hexdigest() != artifact.sha256:
                    return None
            terms = IndexTerms.model_validate(read_json_object(self.index_dir / "terms.json"))
            if terms.schema_version != INDEX_SCHEMA_VERSION or terms.index_version != INDEX_VERSION:
                return None
            return manifest, terms
        except (OSError, FilesystemFormatError, ValidationError, ValueError):
            return None

    def _task_records(self) -> tuple[IndexedTask, ...]:
        self.tasks.rebuild_index()
        try:
            document = read_json_object(self.layout.tasks / "index.json")
        except (OSError, FilesystemFormatError) as exc:
            raise ConflictError("Task Capsule index could not be rebuilt") from exc
        raw_tasks = document.get("tasks")
        if not isinstance(raw_tasks, list):
            raise ConflictError("Task Capsule index is invalid")
        result: list[IndexedTask] = []
        for raw in raw_tasks:
            if not isinstance(raw, dict):
                raise ConflictError("Task Capsule index contains an invalid task")
            identifier = _required_text(raw.get("id"), "Task Capsule ID")
            summary_path = self.layout.task(identifier) / "final" / "summary.md"
            summary = ""
            if summary_path.is_file():
                try:
                    summary = safe_diagnostic(
                        ensure_no_filesystem_links(summary_path).read_text(encoding="utf-8")
                    )[:_MAX_SUMMARY_CHARS]
                except (OSError, UnicodeDecodeError) as exc:
                    raise ConflictError("Task Capsule summary is unreadable") from exc
            result.append(
                IndexedTask(
                    id=identifier,
                    run_id=_required_text(raw.get("run_id"), "Task run ID"),
                    title=_required_text(raw.get("title"), "Task title", default="Untitled task"),
                    status=_required_text(raw.get("status"), "Task status", default="UNKNOWN"),
                    created_at=_optional_text(raw.get("created_at")),
                    completed_at=_optional_text(raw.get("completed_at")),
                    branch=_optional_text(raw.get("branch")),
                    starting_commit=_optional_text(raw.get("starting_commit")),
                    summary=summary,
                )
            )
        return tuple(result)

    def _documents(
        self,
        files: tuple[GraphNode, ...],
        symbols: tuple[GraphNode, ...],
        memory: tuple[DurableMemoryRecord, ...],
        tasks: tuple[IndexedTask, ...],
    ) -> tuple[IndexDocument, ...]:
        documents: list[IndexDocument] = []
        for node in files:
            documents.append(
                IndexDocument(
                    id=f"repository:file:{node.id}",
                    kind=IndexRecordKind.FILE,
                    title=node.name,
                    path=node.file_path,
                    summary=" ".join(
                        value
                        for value in (
                            node.language,
                            _metadata_text(node.metadata.get("role")),
                        )
                        if value
                    ),
                    metadata={
                        "node_id": node.id,
                        "node_kind": str(node.kind),
                        "language": node.language,
                        "source_hash": node.source_hash,
                    },
                )
            )
        for node in symbols:
            qualified = _metadata_text(node.metadata.get("qualified_name"))
            documents.append(
                IndexDocument(
                    id=f"repository:symbol:{node.id}",
                    kind=IndexRecordKind.SYMBOL,
                    title=node.name,
                    path=node.file_path,
                    summary=" ".join(
                        value for value in (str(node.kind), qualified, node.language) if value
                    ),
                    metadata={
                        "node_id": node.id,
                        "node_kind": str(node.kind),
                        "language": node.language,
                        "line_start": node.line_start,
                        "line_end": node.line_end,
                    },
                )
            )
        for record in memory:
            documents.append(
                IndexDocument(
                    id=f"memory:{record.id}",
                    kind=IndexRecordKind.MEMORY,
                    title=record.title,
                    path=f".orqalis/memory/records/{record.id}.md",
                    summary=record.content[:_MAX_SUMMARY_CHARS],
                    metadata={
                        "memory_id": record.id,
                        "category": record.category.value,
                        "source_paths": list(record.source.paths),
                        "introduced_by_task": record.introduced_by_task,
                        "confidence": record.confidence,
                    },
                )
            )
        for task in tasks:
            documents.append(
                IndexDocument(
                    id=f"task:{task.id}",
                    kind=IndexRecordKind.TASK,
                    title=task.title,
                    path=f".orqalis/tasks/{task.id}",
                    summary=task.summary,
                    metadata={
                        "task_id": task.id,
                        "run_id": task.run_id,
                        "status": task.status,
                        "branch": task.branch,
                        "starting_commit": task.starting_commit,
                    },
                )
            )
        result = tuple(sorted(documents, key=lambda item: item.id))
        if len({item.id for item in result}) != len(result):
            raise ConflictError("Project index contains duplicate document identifiers")
        return result

    @staticmethod
    def _terms(documents: tuple[IndexDocument, ...]) -> IndexTerms:
        postings: defaultdict[str, set[str]] = defaultdict(set)
        mapped: dict[str, IndexDocument] = {}
        for document in documents:
            mapped[document.id] = document
            text = " ".join(
                (
                    document.title,
                    document.path or "",
                    document.summary,
                    " ".join(_metadata_strings(document.metadata)),
                )
            )
            for term in _tokenize(text):
                postings[term].add(document.id)
        return IndexTerms(
            documents=dict(sorted(mapped.items())),
            postings={
                term: tuple(sorted(document_ids)) for term, document_ids in sorted(postings.items())
            },
        )

    def _project_identity(self) -> tuple[str, str]:
        project = self.project_manifest.get("project")
        if not isinstance(project, dict):
            raise ConflictError("Project manifest identity is invalid")
        return (
            _required_text(project.get("id"), "Project ID"),
            _required_text(project.get("name"), "Project name"),
        )

    def _storage_target(self, path: Path) -> Path:
        target = self.layout.contained(path)
        store = self.layout.store
        if store.exists() and (store.is_symlink() or store.is_junction()):
            raise PolicyDeniedError("Project store must not be a link or junction")
        resolved_store = store.resolve(strict=False)
        resolved_target = target.resolve(strict=False)
        if resolved_target != resolved_store and not resolved_target.is_relative_to(resolved_store):
            raise PolicyDeniedError("Project index path escapes the selected repository")
        return target


def _required_text(value: object, label: str, *, default: str | None = None) -> str:
    if isinstance(value, str) and value.strip():
        return value
    if default is not None:
        return default
    raise ConflictError(f"{label} is invalid")


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _metadata_text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _metadata_strings(metadata: Mapping[str, object]) -> tuple[str, ...]:
    values: list[str] = []
    for key, value in sorted(metadata.items()):
        values.append(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value is not None:
            values.append(str(value))
    return tuple(values)


def _tokenize(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_TERM.findall(value.casefold())))


def _json_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ConflictError("Project index contains unserializable data") from exc


def _jsonl_bytes(values: Iterable[object]) -> bytes:
    try:
        return b"".join(
            (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode(
                "utf-8"
            )
            for value in values
        )
    except (TypeError, ValueError) as exc:
        raise ConflictError("Project index contains unserializable records") from exc


def _duration_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
