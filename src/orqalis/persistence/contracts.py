"""Storage-neutral persistence contracts for the repo-local architecture.

The existing repository protocols remain the fine-grained compatibility boundary used by
the Orchestrator.  These coarser contracts name the durable filesystem responsibilities
without exposing raw path mutation to application, MCP, API, or UI callers.
"""

from pathlib import Path
from typing import Protocol
from uuid import UUID

from orqalis.memory.ports import MemoryRepository
from orqalis.persistence.approval_ports import ApprovalRepository
from orqalis.persistence.delivery_ports import DeliveryRepository
from orqalis.persistence.event_ports import EventRepository
from orqalis.persistence.execution_ports import ExecutionRepository
from orqalis.persistence.ports import ProjectRepository
from orqalis.persistence.provider_ports import ProviderRepository
from orqalis.persistence.run_ports import RunRepository
from orqalis.persistence.runtime_ports import RuntimeRepository


class ProjectStore(ProjectRepository, Protocol):
    """Project identity/configuration scoped to exactly one repository root."""

    @property
    def root(self) -> Path: ...


class MemoryStore(MemoryRepository, Protocol):
    """Curated/source-backed project knowledge; never transient task state."""


class GraphStore(Protocol):
    """Typed repository structure whose persisted representation is rebuildable."""

    def refresh(self) -> object: ...
    def rebuild(self) -> object: ...


class TaskStore(Protocol):
    """Authoritative Task Capsule aggregate, addressed internally by Run UUID."""

    @property
    def runs(self) -> RunRepository: ...

    @property
    def runtime(self) -> RuntimeRepository: ...

    @property
    def approvals(self) -> ApprovalRepository: ...

    @property
    def execution(self) -> ExecutionRepository: ...

    @property
    def providers(self) -> ProviderRepository: ...

    @property
    def delivery(self) -> DeliveryRepository: ...

    def capsule_id(self, run_id: UUID) -> str | None: ...
    def rebuild_index(self) -> int: ...


class EventStore(EventRepository, Protocol):
    """Append-only structured lifecycle events associated with a Task Capsule."""


class ArtifactStore(Protocol):
    """Evidence/artifact payloads referenced by durable Task Capsule metadata."""

    def artifact_path(self, run_id: UUID, artifact_id: UUID) -> Path: ...
