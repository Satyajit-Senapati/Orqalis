"""Shared filesystem persistence helpers for product-level tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from orqalis.observability.event_bus import ProjectEventBus
from orqalis.persistence.filesystem import FilesystemProjectUnitOfWork, TaskCapsuleStore


def filesystem_uow_factory(
    root: Path, event_bus: ProjectEventBus | None = None
) -> Callable[[], FilesystemProjectUnitOfWork]:
    """Return fresh project-local units of work sharing one root-scoped store."""

    store = TaskCapsuleStore.from_root(root)
    return lambda: FilesystemProjectUnitOfWork(store, event_bus)


__all__ = ["filesystem_uow_factory"]
