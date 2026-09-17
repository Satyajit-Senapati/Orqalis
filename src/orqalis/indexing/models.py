"""Typed contracts for the rebuildable local project index."""

from enum import StrEnum

from pydantic import AwareDatetime, Field

from orqalis.domain.base import Contract, utc_now

INDEX_SCHEMA_VERSION = 1
INDEX_VERSION = "lexical-v1"

IndexMetadataValue = str | int | float | bool | None | list[str]


class IndexRecordKind(StrEnum):
    FILE = "repository_file"
    SYMBOL = "repository_symbol"
    MEMORY = "memory"
    TASK = "task"


class IndexDocument(Contract):
    id: str = Field(min_length=1)
    kind: IndexRecordKind
    title: str = Field(min_length=1)
    path: str | None = None
    summary: str = ""
    metadata: dict[str, IndexMetadataValue] = Field(default_factory=dict)


class IndexTerms(Contract):
    schema_version: int = INDEX_SCHEMA_VERSION
    index_version: str = INDEX_VERSION
    documents: dict[str, IndexDocument] = Field(default_factory=dict)
    postings: dict[str, tuple[str, ...]] = Field(default_factory=dict)


class IndexedTask(Contract):
    id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: str = Field(min_length=1)
    created_at: str | None = None
    completed_at: str | None = None
    branch: str | None = None
    starting_commit: str | None = None
    summary: str = ""


class IndexBuildMetrics(Contract):
    duration_ms: float = Field(ge=0)
    documents_indexed: int = Field(ge=0)
    terms_indexed: int = Field(ge=0)
    file_records: int = Field(ge=0)
    symbol_records: int = Field(ge=0)
    relation_records: int = Field(ge=0)
    memory_records: int = Field(ge=0)
    task_records: int = Field(ge=0)
    graph_processed_files: int = Field(ge=0)
    graph_cache_hits: int = Field(ge=0)
    graph_cache_misses: int = Field(ge=0)


class IndexArtifact(Contract):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(ge=0)
    records: int = Field(ge=0)


class IndexManifest(Contract):
    schema_version: int = INDEX_SCHEMA_VERSION
    index_version: str = INDEX_VERSION
    generated_at: AwareDatetime = Field(default_factory=utc_now)
    project_id: str = Field(min_length=1)
    project_name: str = Field(min_length=1)
    indexed_commit: str | None = None
    indexed_branch: str | None = None
    graph_schema_version: int = Field(ge=1)
    parser_version: str = Field(min_length=1)
    artifacts: dict[str, IndexArtifact]
    metrics: IndexBuildMetrics


class ProjectIndexBuildResult(Contract):
    manifest: IndexManifest
    metrics: IndexBuildMetrics


class ProjectIndexMatch(Contract):
    document: IndexDocument
    score: float = Field(ge=0)
    matched_terms: tuple[str, ...] = ()
