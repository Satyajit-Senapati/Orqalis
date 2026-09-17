"""Complete project unit of work backed by one repository-local store."""

from __future__ import annotations

from pathlib import Path
from types import TracebackType

from orqalis.observability.event_bus import ProjectEventBus
from orqalis.persistence.filesystem.auxiliary_stores import (
    FilesystemDeliveryRepository,
    FilesystemExecutionRepository,
    FilesystemProviderRepository,
)
from orqalis.persistence.filesystem.memory_store import FilesystemMemoryRepository
from orqalis.persistence.filesystem.task_store import (
    FilesystemApprovalRepository,
    FilesystemEventRepository,
    FilesystemProjectRepository,
    FilesystemRunRepository,
    FilesystemRuntimeRepository,
    TaskCapsuleSession,
    TaskCapsuleStore,
)


class FilesystemProjectUnitOfWork:
    """Storage-neutral UoW assembled over one project-local Task Capsule session.

    Task state commits before curated/source memory. If memory persistence fails, the
    authoritative task lifecycle remains recoverable and memory can be regenerated or
    curated again; the inverse ordering could leave memory referring to a task commit
    that never became durable.
    """

    def __init__(self, store: TaskCapsuleStore, event_bus: ProjectEventBus | None = None) -> None:
        self.store = store
        self.event_bus = event_bus
        self.session = TaskCapsuleSession(store)
        self.projects = FilesystemProjectRepository(self.session)
        self.approvals = FilesystemApprovalRepository(self.session)
        self.memory = FilesystemMemoryRepository(store.layout)
        self.runs = FilesystemRunRepository(self.session)
        self.events = FilesystemEventRepository(self.session)
        self.delivery = FilesystemDeliveryRepository(self.session)
        self.execution = FilesystemExecutionRepository(self.session)
        self.providers = FilesystemProviderRepository(self.session)
        self.runtime = FilesystemRuntimeRepository(self.session)
        self._closed = False

    @classmethod
    def from_root(
        cls, root: Path, event_bus: ProjectEventBus | None = None
    ) -> FilesystemProjectUnitOfWork:
        return cls(TaskCapsuleStore.from_root(root), event_bus)

    def __enter__(self) -> FilesystemProjectUnitOfWork:
        self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                self.rollback()
        finally:
            self.close()

    def commit(self) -> None:
        self._ensure_open()
        pending_events = self.session.pending_events()
        self.session.commit()
        self.memory.commit()
        if self.event_bus is not None:
            self.event_bus.publish(pending_events)

    def rollback(self) -> None:
        self._ensure_open()
        try:
            self.memory.rollback()
        finally:
            self.session.rollback()

    def close(self) -> None:
        if self._closed:
            return
        try:
            try:
                # Discard an uncommitted memory view before releasing its project lock.
                self.memory.rollback()
            finally:
                self.memory.close()
        finally:
            # The controller lease intentionally remains held until every adapter closes.
            self.session.close()
            self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Filesystem project unit of work is closed")


__all__ = ["FilesystemProjectUnitOfWork"]
