from types import TracebackType
from typing import Protocol

from orqalis.memory.ports import MemoryRepository
from orqalis.persistence.approval_ports import ApprovalRepository
from orqalis.persistence.delivery_ports import DeliveryRepository
from orqalis.persistence.event_ports import EventRepository
from orqalis.persistence.execution_ports import ExecutionRepository
from orqalis.persistence.ports import ProjectRepository
from orqalis.persistence.provider_ports import ProviderRepository
from orqalis.persistence.run_ports import RunRepository
from orqalis.persistence.runtime_ports import RuntimeRepository


class ProjectUnitOfWork(Protocol):
    @property
    def approvals(self) -> ApprovalRepository: ...

    @property
    def projects(self) -> ProjectRepository: ...

    @property
    def memory(self) -> MemoryRepository: ...

    @property
    def runs(self) -> RunRepository: ...

    @property
    def events(self) -> EventRepository: ...

    @property
    def runtime(self) -> RuntimeRepository: ...

    @property
    def providers(self) -> ProviderRepository: ...

    @property
    def execution(self) -> ExecutionRepository: ...

    @property
    def delivery(self) -> DeliveryRepository: ...

    def __enter__(self) -> "ProjectUnitOfWork": ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
