from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from orqalis.persistence.approvals import SQLApprovalRepository
from orqalis.persistence.delivery import SQLDeliveryRepository
from orqalis.persistence.events import SQLEventRepository
from orqalis.persistence.execution import SQLExecutionRepository
from orqalis.persistence.memory import SQLMemoryRepository
from orqalis.persistence.projects import SQLProjectRepository
from orqalis.persistence.providers import SQLProviderRepository
from orqalis.persistence.runs import SQLRunRepository
from orqalis.persistence.runtime import SQLRuntimeRepository


class SQLProjectUnitOfWork:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.session = sessions()
        self.projects = SQLProjectRepository(self.session)
        self.approvals = SQLApprovalRepository(self.session)
        self.memory = SQLMemoryRepository(self.session)
        self.runs = SQLRunRepository(self.session)
        self.events = SQLEventRepository(self.session)
        self.delivery = SQLDeliveryRepository(self.session)
        self.execution = SQLExecutionRepository(self.session)
        self.providers = SQLProviderRepository(self.session)
        self.runtime = SQLRuntimeRepository(self.session)

    def __enter__(self) -> "SQLProjectUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.session.close()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
