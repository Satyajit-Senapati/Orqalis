"""Selective project context construction."""

from typing import TYPE_CHECKING

from orqalis.context.models import (
    GraphContextItem,
    HistoricalTaskContext,
    MemoryContextItem,
    ProjectContextPack,
)

if TYPE_CHECKING:
    from orqalis.context.builder import ProjectContextBuilder
    from orqalis.context.service import TaskContextService


def __getattr__(name: str) -> object:
    """Load graph-dependent services lazily to keep package imports acyclic."""

    if name == "ProjectContextBuilder":
        from orqalis.context.builder import ProjectContextBuilder

        return ProjectContextBuilder
    if name == "TaskContextService":
        from orqalis.context.service import TaskContextService

        return TaskContextService
    raise AttributeError(name)


__all__ = [
    "GraphContextItem",
    "HistoricalTaskContext",
    "MemoryContextItem",
    "ProjectContextBuilder",
    "ProjectContextPack",
    "TaskContextService",
]
