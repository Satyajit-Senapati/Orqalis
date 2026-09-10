from enum import StrEnum
from pathlib import Path
from uuid import UUID

from pydantic import AwareDatetime, Field

from orqalis.domain.base import Contract, Entity, utc_now


class MemoryStatus(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    SUPERSEDED = "superseded"
    INVALIDATED = "invalidated"


class MemoryType(StrEnum):
    REPOSITORY_MAP = "repository_map"
    ARCHITECTURE = "architecture"
    CONVENTION = "convention"
    DECISION = "decision"
    DOMAIN = "domain"
    KNOWN_ISSUE = "known_issue"
    PREVIOUS_RUN = "previous_run"


class ProjectSnapshot(Entity):
    project_id: UUID
    indexed_commit_sha: str
    status: str = "current"
    repo_fingerprint: str
    files_scanned: int = Field(ge=0)
    invalidations: int = Field(default=0, ge=0)


class RepositoryFile(Entity):
    project_id: UUID
    path: str
    language: str | None = None
    role: str
    content_hash: str
    last_seen_commit: str


class MemoryItem(Entity):
    project_id: UUID
    type: MemoryType
    title: str
    content: str
    confidence: float = Field(default=1, ge=0, le=1)
    status: MemoryStatus = MemoryStatus.ACTIVE
    source_commit: str
    introduced_by_run: UUID | None = None
    last_verified_at: AwareDatetime = Field(default_factory=utc_now)
    superseded_by: UUID | None = None


class MemorySource(Entity):
    memory_item_id: UUID
    source_type: str = "file"
    source_ref: str
    content_hash: str
    commit_sha: str


class ArchitectureEntity(Entity):
    project_id: UUID
    entity_type: str = "file"
    name: str
    source_refs: tuple[str, ...]


class ArchitectureRelation(Entity):
    project_id: UUID
    source_entity_id: UUID
    relation_type: str
    target_entity_id: UUID
    confidence: float = Field(default=1, ge=0, le=1)
    source_refs: tuple[str, ...]


class MemoryMatch(Contract):
    item: MemoryItem
    sources: tuple[MemorySource, ...]
    score: float


class MemoryHealth(Contract):
    project_id: UUID
    indexed_commit: str | None
    current_commit: str
    fresh: bool
    dirty_paths: tuple[str, ...]
    active_items: int = Field(ge=0)


class ContextPack(Contract):
    project_id: UUID
    task: str
    items: tuple[MemoryMatch, ...]
    relevant_files: tuple[str, ...]
    freshness: MemoryHealth
    confidence: float = Field(ge=0, le=1)
    targeted_inspection_paths: tuple[str, ...]
    requires_inspection: bool
    size_chars: int = Field(ge=0)


class MemoryRefresh(Contract):
    snapshot: ProjectSnapshot
    scanned_paths: tuple[str, ...] = ()
    invalidated_items: int = Field(default=0, ge=0)
    reused: bool = False


class ProjectBrain(Contract):
    project_id: UUID
    inspected_root: Path
    query: str
    freshness: MemoryHealth
    matches: tuple[MemoryMatch, ...]
    entities: tuple[ArchitectureEntity, ...]
    relations: tuple[ArchitectureRelation, ...]
