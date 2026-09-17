"""Typed contracts for Orqalis-owned repository graphs."""

from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from orqalis.domain.base import Contract, utc_now

GraphMetadataValue = str | int | float | bool | None | list[str]


class GraphNodeKind(StrEnum):
    FILE = "FILE"
    MODULE = "MODULE"
    PACKAGE = "PACKAGE"
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"
    INTERFACE = "INTERFACE"
    API_ROUTE = "API_ROUTE"
    DATABASE_TABLE = "DATABASE_TABLE"
    CONFIGURATION = "CONFIGURATION"
    TEST = "TEST"
    DOCUMENTATION = "DOCUMENTATION"
    REFERENCE = "REFERENCE"


class GraphRelation(StrEnum):
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    IMPLEMENTS = "IMPLEMENTS"
    EXTENDS = "EXTENDS"
    USES = "USES"
    DEFINES = "DEFINES"
    REFERENCES = "REFERENCES"
    TESTS = "TESTS"
    CONFIGURES = "CONFIGURES"
    DEPENDS_ON = "DEPENDS_ON"
    ROUTES_TO = "ROUTES_TO"
    READS_FROM = "READS_FROM"
    WRITES_TO = "WRITES_TO"


class GraphProvenance(StrEnum):
    EXTRACTED = "EXTRACTED"
    INFERRED = "INFERRED"


class GraphNode(Contract):
    id: str = Field(min_length=1)
    kind: GraphNodeKind | str
    name: str = Field(min_length=1)
    file_path: str | None = None
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    language: str | None = None
    metadata: dict[str, GraphMetadataValue] = Field(default_factory=dict)
    source_hash: str | None = None

    @model_validator(mode="after")
    def valid_location(self) -> Self:
        if (self.line_start is None) != (self.line_end is None):
            raise ValueError("Graph node line bounds must both be set or both be absent")
        if (
            self.line_start is not None
            and self.line_end is not None
            and self.line_end < self.line_start
        ):
            raise ValueError("Graph node line_end must not precede line_start")
        return self


class GraphEdge(Contract):
    id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    relation: GraphRelation | str
    provenance: GraphProvenance
    confidence: float = Field(ge=0, le=1)
    evidence: tuple[str, ...] = ()


class ProjectGraph(Contract):
    schema_version: int = Field(default=1, ge=1)
    parser_version: str = Field(min_length=1)
    generated_at: AwareDatetime = Field(default_factory=utc_now)
    nodes: tuple[GraphNode, ...] = ()
    edges: tuple[GraphEdge, ...] = ()


class GraphManifest(Contract):
    schema_version: int = Field(default=1, ge=1)
    parser_version: str = Field(min_length=1)
    indexed_commit: str | None = None
    indexed_head: str | None = None
    indexed_branch: str | None = None
    dirty_paths: tuple[str, ...] = ()
    file_hashes: dict[str, str] = Field(default_factory=dict)
    graph_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    last_indexed_at: AwareDatetime = Field(default_factory=utc_now)


class GraphRefreshMetrics(Contract):
    processed_files: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    cache_misses: int = Field(ge=0)
    deleted_files: int = Field(ge=0)
    total_files: int = Field(ge=0)
    duration_ms: float = Field(ge=0)
    changed_paths: tuple[str, ...] = ()


class GraphRefreshResult(Contract):
    graph: ProjectGraph
    manifest: GraphManifest
    metrics: GraphRefreshMetrics
