"""Bounded context contracts shared by assistant/provider adapters."""

from pydantic import Field

from orqalis.domain.base import Contract
from orqalis.graph.models import GraphNode
from orqalis.memory.curated import DurableMemoryRecord, MemoryFreshness


class MemoryContextItem(Contract):
    record: DurableMemoryRecord
    freshness: MemoryFreshness
    score: float = Field(ge=0)


class GraphContextItem(Contract):
    node: GraphNode
    score: float = Field(ge=0)
    distance: int | None = Field(default=None, ge=0)
    neighbors: tuple[str, ...] = ()


class HistoricalTaskContext(Contract):
    id: str
    title: str
    status: str
    branch: str | None = None
    completed_at: str | None = None
    summary: str | None = None
    score: float = Field(ge=0)


class ProjectContextPack(Contract):
    schema_version: int = 1
    task: str = Field(min_length=1)
    project_id: str
    project_name: str
    branch: str | None = None
    head_commit: str
    dirty_paths: tuple[str, ...] = ()
    relevant_files: tuple[str, ...] = ()
    graph: tuple[GraphContextItem, ...] = ()
    memory: tuple[MemoryContextItem, ...] = ()
    decisions: tuple[str, ...] = ()
    related_tasks: tuple[HistoricalTaskContext, ...] = ()
    size_chars: int = Field(ge=0)
    max_chars: int = Field(ge=1000)
    truncated: bool = False
