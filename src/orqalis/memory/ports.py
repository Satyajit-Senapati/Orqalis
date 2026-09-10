from typing import Protocol
from uuid import UUID

from orqalis.domain.memory import (
    ArchitectureEntity,
    ArchitectureRelation,
    ContextPack,
    MemoryItem,
    MemoryMatch,
    MemorySource,
    ProjectSnapshot,
    RepositoryFile,
)
from orqalis.domain.project import Project
from orqalis.memory.indexing import IndexedContent


class EmbeddingProvider(Protocol):
    model_id: str
    dimensions: int

    def embed(self, text: str) -> tuple[float, ...]: ...


class MemoryRepository(Protocol):
    def lock_project(self, project_id: UUID) -> None: ...
    def latest_snapshot(self, project_id: UUID) -> ProjectSnapshot | None: ...
    def save_snapshot(self, snapshot: ProjectSnapshot) -> None: ...
    def files(self, project_id: UUID) -> tuple[RepositoryFile, ...]: ...

    def current_file(self, project_id: UUID, path: str) -> RepositoryFile | None: ...
    def save_file(self, file: RepositoryFile) -> None: ...
    def remove_file(self, project_id: UUID, path: str) -> None: ...
    def invalidate_path(self, project_id: UUID, path: str, replacement: UUID | None) -> int: ...
    def add_item(
        self,
        item: MemoryItem,
        source: MemorySource,
        embedding: tuple[float, ...] | None,
        embedding_model: str | None,
    ) -> None: ...
    def attribute_commit(self, project_id: UUID, commit: str, run_id: UUID) -> None: ...
    def items_for_run(self, run_id: UUID) -> tuple[MemoryItem, ...]: ...
    def active_count(self, project_id: UUID) -> int: ...
    def search(
        self,
        project_id: UUID,
        terms: tuple[str, ...],
        limit: int,
        embedding: tuple[float, ...] | None = None,
        embedding_model: str | None = None,
    ) -> tuple[MemoryMatch, ...]: ...
    def save_entity(self, entity: ArchitectureEntity) -> None: ...
    def save_relation(self, relation: ArchitectureRelation) -> None: ...
    def graph(
        self, project_id: UUID
    ) -> tuple[tuple[ArchitectureEntity, ...], tuple[ArchitectureRelation, ...]]: ...


class MemoryIndexer(Protocol):
    MAX_BYTES: int

    def allows(self, path: str) -> bool: ...
    def index(self, path: str, content: bytes) -> IndexedContent | None: ...


class MemoryRetriever(Protocol):
    def search(self, project: Project, query: str, limit: int = 10) -> tuple[MemoryMatch, ...]: ...


class ContextService(Protocol):
    def context(self, project: Project, task: str, max_chars: int = 20_000) -> ContextPack: ...
