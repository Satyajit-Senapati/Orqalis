"""Rebuildable legacy-memory projection cache.

CuratedMemoryStore owns durable knowledge and ProjectGraphEngine owns repository
structure. This adapter preserves legacy search contracts only. Every artifact it writes
is under .orqalis/cache and is safe to delete.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from orqalis.domain.errors import ConflictError, NotFoundError, PolicyDeniedError
from orqalis.domain.memory import (
    ArchitectureEntity,
    ArchitectureRelation,
    MemoryItem,
    MemoryMatch,
    MemorySource,
    MemoryStatus,
    ProjectSnapshot,
    RepositoryFile,
)
from orqalis.persistence.filesystem.io import (
    FilesystemFormatError,
    atomic_write_bytes,
    atomic_write_json,
    ensure_no_filesystem_links,
    read_json_object,
    read_jsonl,
)
from orqalis.persistence.filesystem.layout import ProjectLayout
from orqalis.persistence.filesystem.locking import FileLock
from orqalis.security.redaction import safe_diagnostic

MEMORY_ADAPTER_SCHEMA_VERSION = 1


@dataclass(slots=True)
class _StoredMemory:
    item: MemoryItem
    sources: list[MemorySource] = field(default_factory=list)
    embedding: tuple[float, ...] | None = None
    embedding_model: str | None = None


def _record_bytes(record: _StoredMemory) -> bytes:
    metadata = {
        "schema_version": MEMORY_ADAPTER_SCHEMA_VERSION,
        "item": record.item.model_dump(mode="json", exclude={"content"}),
        "sources": [source.model_dump(mode="json") for source in record.sources],
        "embedding_model": record.embedding_model,
    }
    header = json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False)
    return (
        f"---\n{header}\n---\n\n# {record.item.title}\n\n{record.item.content.rstrip()}\n"
    ).encode()


def _read_record(path: Path) -> _StoredMemory:
    try:
        text = ensure_no_filesystem_links(path).read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            raise ValueError
        raw, body = text[4:].split("\n---\n", 1)
        metadata = json.loads(raw)
        if metadata.get("schema_version") != MEMORY_ADAPTER_SCHEMA_VERSION:
            raise ValueError
        item_data = metadata["item"]
        title = item_data["title"]
        content = body.strip()
        heading = f"# {title}"
        if content.startswith(heading):
            content = content[len(heading) :].strip()
        item = MemoryItem.model_validate({**item_data, "content": content})
        sources = [MemorySource.model_validate(value) for value in metadata["sources"]]
        model = metadata.get("embedding_model")
        if model is not None and not isinstance(model, str):
            raise ValueError
        return _StoredMemory(item=item, sources=sources, embedding_model=model)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
        raise ConflictError("Project memory record is invalid") from exc


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return max(0.0, numerator / (left_norm * right_norm))


class FilesystemMemoryRepository:
    """Transactional view of a disposable source-search projection.

    This repository must never contain curated memory or task outcomes. Its Markdown
    records are derived source summaries, not Project Memory.
    """

    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self._records: dict[UUID, _StoredMemory] = {}
        self._snapshots: list[ProjectSnapshot] = []
        self._files: dict[tuple[UUID, str], RepositoryFile] = {}
        self._entities: dict[UUID, ArchitectureEntity] = {}
        self._relations: dict[UUID, ArchitectureRelation] = {}
        self._lock: FileLock | None = None
        self._dirty = False
        # Readers need a coherent view across derived projections while another
        # process may be rebuilding them.
        with FileLock(self.layout.lock("source-projection")):
            self._relocate_legacy_artifacts()
            self._load()

    @property
    def _records_dir(self) -> Path:
        return self.layout.contained(self.layout.cache / "search" / "source-records")

    @property
    def _snapshot_path(self) -> Path:
        return self.layout.contained(self.layout.cache / "search" / "source-snapshots.json")

    @property
    def _files_path(self) -> Path:
        # Compatibility bookkeeping is rebuildable and must not collide with the
        # ProjectIndex-owned `.orqalis/index/files.jsonl` graph-node artifact.
        return self.layout.contained(self.layout.cache / "search" / "compat-repository-files.jsonl")

    @property
    def _graph_path(self) -> Path:
        return self.layout.contained(self.layout.cache / "graph" / "legacy-projection.json")

    @property
    def _embedding_path(self) -> Path:
        return self.layout.contained(self.layout.cache / "search" / "embeddings.json")

    def _relocate_legacy_artifacts(self) -> None:
        """Move pre-consolidation derived artifacts out of canonical memory."""

        legacy_records = self.layout.contained(self.layout.memory / "records")
        if legacy_records.is_dir():
            for source in sorted(legacy_records.glob("SRC-*.md")):
                payload = ensure_no_filesystem_links(source).read_bytes()
                try:
                    _read_record(source)
                except ConflictError:
                    source.unlink()
                    continue
                self._records_dir.mkdir(parents=True, exist_ok=True)
                atomic_write_bytes(self._records_dir / source.name, payload)
                source.unlink()
        legacy_snapshot = self.layout.contained(self.layout.memory / "history" / "snapshots.json")
        if legacy_snapshot.is_file():
            try:
                document = read_json_object(legacy_snapshot)
            except FilesystemFormatError:
                legacy_snapshot.unlink()
            else:
                atomic_write_json(self._snapshot_path, document)
                legacy_snapshot.unlink()
        legacy_graph = self.layout.contained(
            self.layout.memory / "graph" / "compatibility-graph.json"
        )
        if legacy_graph.is_file():
            try:
                document = read_json_object(legacy_graph)
            except FilesystemFormatError:
                legacy_graph.unlink()
            else:
                atomic_write_json(self._graph_path, document)
                legacy_graph.unlink()

    def _load(self) -> None:
        file_cache_present = self._files_path.is_file()
        if self._records_dir.is_dir():
            for path in sorted(self._records_dir.glob("SRC-*.md")):
                record = _read_record(path)
                if record.item.id in self._records:
                    raise ConflictError("Duplicate project memory record")
                self._records[record.item.id] = record
        if self._snapshot_path.is_file():
            try:
                document = read_json_object(self._snapshot_path)
                if document.get("schema_version") != MEMORY_ADAPTER_SCHEMA_VERSION:
                    raise ConflictError("Unsupported memory history schema")
                values = document.get("snapshots")
                if not isinstance(values, list):
                    raise ConflictError("Memory snapshot history is invalid")
                self._snapshots = [ProjectSnapshot.model_validate(value) for value in values]
            except (FilesystemFormatError, ValidationError) as exc:
                raise ConflictError("Memory snapshot history is invalid") from exc
        try:
            for value in read_jsonl(self._files_path):
                version = value.pop("schema_version", None)
                if version != MEMORY_ADAPTER_SCHEMA_VERSION:
                    raise ConflictError("Unsupported repository file index schema")
                item = RepositoryFile.model_validate(value)
                self._files[(item.project_id, item.path)] = item
        except (FilesystemFormatError, ValidationError) as exc:
            raise ConflictError("Repository file index is invalid") from exc
        if self._snapshots and not file_cache_present:
            # The file inventory is disposable. Dropping snapshot receipts forces
            # MemoryService to deterministically scan the current Git tree and
            # reconstruct it instead of trusting an incomplete cache.
            self._snapshots = []
        if self._graph_path.is_file():
            try:
                document = read_json_object(self._graph_path)
                if document.get("schema_version") != MEMORY_ADAPTER_SCHEMA_VERSION:
                    raise ConflictError("Unsupported compatibility graph schema")
                entities = document.get("entities")
                relations = document.get("relations")
                if not isinstance(entities, list) or not isinstance(relations, list):
                    raise ConflictError("Compatibility graph is invalid")
                self._entities = {
                    item.id: item
                    for value in entities
                    for item in (ArchitectureEntity.model_validate(value),)
                }
                self._relations = {
                    item.id: item
                    for value in relations
                    for item in (ArchitectureRelation.model_validate(value),)
                }
            except (FilesystemFormatError, ValidationError) as exc:
                raise ConflictError("Compatibility graph is invalid") from exc
        if self._embedding_path.is_file():
            try:
                document = read_json_object(self._embedding_path)
                if document.get("schema_version") != MEMORY_ADAPTER_SCHEMA_VERSION:
                    return
                values = document.get("embeddings")
                if not isinstance(values, dict):
                    return
                for raw_id, value in values.items():
                    item_id = UUID(raw_id)
                    stored = self._records.get(item_id)
                    if stored is None or not isinstance(value, dict):
                        continue
                    vector, model = value.get("vector"), value.get("model")
                    if (
                        isinstance(vector, list)
                        and all(isinstance(number, (int, float)) for number in vector)
                        and isinstance(model, str)
                    ):
                        stored.embedding = tuple(float(number) for number in vector)
                        stored.embedding_model = model
            except (ValueError, FilesystemFormatError):
                # Cache corruption never destroys canonical project knowledge.
                pass

    def _reset_loaded_state(self) -> None:
        self._records.clear()
        self._snapshots.clear()
        self._files.clear()
        self._entities.clear()
        self._relations.clear()

    def _prepare_write(self) -> None:
        if self._lock is not None:
            return
        lock = FileLock(self.layout.lock("source-projection"))
        lock.acquire()
        self._lock = lock
        try:
            # This repository may have been constructed before another process
            # committed. Reload only after acquiring the project memory lock.
            self._reset_loaded_state()
            self._load()
        except BaseException:
            lock.release()
            self._lock = None
            raise

    def lock_project(self, project_id: UUID) -> None:
        self._prepare_write()
        identity = self.layout.project / "identity.yaml"
        if not identity.is_file():
            raise NotFoundError("Project not found")
        document = read_json_object(identity)
        if document.get("id") != str(project_id):
            raise NotFoundError("Project not found")

    def latest_snapshot(self, project_id: UUID) -> ProjectSnapshot | None:
        values = [item for item in self._snapshots if item.project_id == project_id]
        return max(values, key=lambda item: item.created_at) if values else None

    def save_snapshot(self, snapshot: ProjectSnapshot) -> None:
        self._prepare_write()
        self._snapshots.append(snapshot)
        self._dirty = True

    def files(self, project_id: UUID) -> tuple[RepositoryFile, ...]:
        return tuple(
            sorted(
                (item for item in self._files.values() if item.project_id == project_id),
                key=lambda item: item.path,
            )
        )

    def current_file(self, project_id: UUID, path: str) -> RepositoryFile | None:
        return self._files.get((project_id, path))

    def save_file(self, file: RepositoryFile) -> None:
        self._prepare_write()
        self._files[(file.project_id, file.path)] = file
        self._dirty = True

    def remove_file(self, project_id: UUID, path: str) -> None:
        self._prepare_write()
        self._files.pop((project_id, path), None)
        removed = {
            item.id
            for item in self._entities.values()
            if item.project_id == project_id and item.name == path
        }
        self._entities = {key: value for key, value in self._entities.items() if key not in removed}
        self._relations = {
            key: value
            for key, value in self._relations.items()
            if value.source_entity_id not in removed and value.target_entity_id not in removed
        }
        self._dirty = True

    def invalidate_path(self, project_id: UUID, path: str, replacement: UUID | None) -> int:
        self._prepare_write()
        affected = 0
        for key, record in tuple(self._records.items()):
            if (
                record.item.project_id != project_id
                or record.item.status != MemoryStatus.ACTIVE
                or key == replacement
                or not any(source.source_ref == path for source in record.sources)
            ):
                continue
            record.item = record.item.model_copy(
                update={
                    "status": MemoryStatus.SUPERSEDED if replacement else MemoryStatus.INVALIDATED,
                    "superseded_by": replacement,
                }
            )
            affected += 1
        self._dirty = self._dirty or bool(affected)
        return affected

    def add_item(
        self,
        item: MemoryItem,
        source: MemorySource,
        embedding: tuple[float, ...] | None,
        embedding_model: str | None,
    ) -> None:
        self._prepare_write()
        payload = item.model_dump_json() + source.model_dump_json()
        if safe_diagnostic(payload) != payload:
            raise PolicyDeniedError("Derived source projection cannot contain credentials")
        existing = self._records.get(item.id)
        candidate = _StoredMemory(item, [source], embedding, embedding_model)
        if existing is not None:
            if existing != candidate:
                raise ConflictError("Memory identity already exists")
            return
        self._records[item.id] = candidate
        self._dirty = True

    def missing_embeddings(
        self, project_id: UUID, embedding_model: str, limit: int = 100
    ) -> tuple[MemoryItem, ...]:
        values = (
            record.item
            for record in self._records.values()
            if record.item.project_id == project_id
            and record.item.status == MemoryStatus.ACTIVE
            and record.embedding_model == embedding_model
            and record.embedding is None
        )
        return tuple(sorted(values, key=lambda item: str(item.id))[:limit])

    def save_embedding(
        self,
        project_id: UUID,
        item_id: UUID,
        embedding: tuple[float, ...],
        embedding_model: str,
    ) -> None:
        self._prepare_write()
        record = self._records.get(item_id)
        if (
            record
            and record.item.project_id == project_id
            and record.item.status == MemoryStatus.ACTIVE
            and record.embedding_model == embedding_model
            and record.embedding is None
        ):
            record.embedding = embedding
            self._dirty = True

    def attribute_commit(self, project_id: UUID, commit: str, run_id: UUID) -> None:
        self._prepare_write()
        for record in self._records.values():
            if (
                record.item.project_id == project_id
                and record.item.source_commit == commit
                and record.item.introduced_by_run is None
            ):
                record.item = record.item.model_copy(update={"introduced_by_run": run_id})
                self._dirty = True

    def items_for_run(self, run_id: UUID) -> tuple[MemoryItem, ...]:
        return tuple(
            sorted(
                (
                    record.item
                    for record in self._records.values()
                    if record.item.introduced_by_run == run_id
                ),
                key=lambda item: (item.created_at, str(item.id)),
            )
        )

    def active_count(self, project_id: UUID) -> int:
        return sum(
            record.item.project_id == project_id and record.item.status == MemoryStatus.ACTIVE
            for record in self._records.values()
        )

    def search(
        self,
        project_id: UUID,
        terms: tuple[str, ...],
        limit: int,
        embedding: tuple[float, ...] | None = None,
        embedding_model: str | None = None,
        excluded_ids: tuple[UUID, ...] = (),
    ) -> tuple[MemoryMatch, ...]:
        excluded = set(excluded_ids)
        matches: list[MemoryMatch] = []
        for record in self._records.values():
            if (
                record.item.project_id != project_id
                or record.item.status != MemoryStatus.ACTIVE
                or record.item.id in excluded
            ):
                continue
            text = f"{record.item.title} {record.item.content}".casefold()
            lexical = sum(term in text for term in terms) / max(1, len(terms))
            semantic_candidate = bool(
                embedding and record.embedding and embedding_model == record.embedding_model
            )
            semantic = (
                _cosine(record.embedding, embedding)
                if semantic_candidate and record.embedding and embedding
                else 0.0
            )
            if terms and lexical == 0 and not semantic_candidate:
                continue
            matches.append(
                MemoryMatch(
                    item=record.item,
                    sources=tuple(sorted(record.sources, key=lambda item: item.source_ref)),
                    score=max(lexical, semantic),
                )
            )
        return tuple(sorted(matches, key=lambda item: (-item.score, item.item.title))[:limit])

    def save_entity(self, entity: ArchitectureEntity) -> None:
        self._prepare_write()
        same_name = next(
            (
                item
                for item in self._entities.values()
                if item.project_id == entity.project_id and item.name == entity.name
            ),
            None,
        )
        if same_name is None:
            self._entities[entity.id] = entity
            self._dirty = True

    def save_relation(self, relation: ArchitectureRelation) -> None:
        self._prepare_write()
        duplicate = any(
            item.source_entity_id == relation.source_entity_id
            and item.relation_type == relation.relation_type
            and item.target_entity_id == relation.target_entity_id
            for item in self._relations.values()
        )
        if not duplicate:
            self._relations[relation.id] = relation
            self._dirty = True

    def graph(
        self, project_id: UUID
    ) -> tuple[tuple[ArchitectureEntity, ...], tuple[ArchitectureRelation, ...]]:
        entities = tuple(
            sorted(
                (item for item in self._entities.values() if item.project_id == project_id),
                key=lambda item: item.name,
            )
        )
        relations = tuple(
            sorted(
                (item for item in self._relations.values() if item.project_id == project_id),
                key=lambda item: str(item.id),
            )
        )
        return entities, relations

    def commit(self) -> None:
        if not self._dirty:
            return
        if self._lock is None:  # pragma: no cover - every mutation acquires first
            raise RuntimeError("Memory writes require the project memory lock")
        self._records_dir.mkdir(parents=True, exist_ok=True)
        expected: set[Path] = set()
        for identifier, record in self._records.items():
            path = self._records_dir / f"SRC-{identifier}.md"
            expected.add(path)
            atomic_write_bytes(path, _record_bytes(record))
        for path in self._records_dir.glob("SRC-*.md"):
            if path not in expected:
                path.unlink()
        atomic_write_json(
            self._snapshot_path,
            {
                "schema_version": MEMORY_ADAPTER_SCHEMA_VERSION,
                "snapshots": [item.model_dump(mode="json") for item in self._snapshots],
            },
        )
        lines = [
            json.dumps(
                {"schema_version": MEMORY_ADAPTER_SCHEMA_VERSION, **item.model_dump(mode="json")},
                separators=(",", ":"),
                sort_keys=True,
            )
            for item in sorted(self._files.values(), key=lambda value: value.path)
        ]
        atomic_write_bytes(self._files_path, (("\n".join(lines) + "\n") if lines else "").encode())
        atomic_write_json(
            self._graph_path,
            {
                "schema_version": MEMORY_ADAPTER_SCHEMA_VERSION,
                "entities": [
                    item.model_dump(mode="json")
                    for item in sorted(self._entities.values(), key=lambda value: value.name)
                ],
                "relations": [
                    item.model_dump(mode="json")
                    for item in sorted(self._relations.values(), key=lambda value: str(value.id))
                ],
            },
        )
        atomic_write_json(
            self._embedding_path,
            {
                "schema_version": MEMORY_ADAPTER_SCHEMA_VERSION,
                "embeddings": {
                    str(identifier): {"model": record.embedding_model, "vector": record.embedding}
                    for identifier, record in self._records.items()
                    if record.embedding is not None and record.embedding_model is not None
                },
            },
        )
        self._dirty = False

    def rollback(self) -> None:
        if self._dirty:
            self._reset_loaded_state()
            self._dirty = False
            self._load()

    def close(self) -> None:
        if self._lock is not None:
            self._lock.release()
            self._lock = None
