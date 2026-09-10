from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from orqalis.domain.provider import ProviderExecution
from orqalis.persistence.provider_models import ProviderExecutionRow


class SQLProviderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, invocation_id: UUID) -> ProviderExecution | None:
        row = self.session.get(ProviderExecutionRow, invocation_id)
        return ProviderExecution.model_validate(row, from_attributes=True) if row else None

    def save(self, invocation: ProviderExecution) -> None:
        values = invocation.model_dump(exclude={"result"})
        values["result"] = invocation.result.model_dump(mode="json") if invocation.result else None
        self.session.merge(ProviderExecutionRow(**values))
        self.session.flush()

    def list(self, run_id: UUID) -> tuple[ProviderExecution, ...]:
        return tuple(
            ProviderExecution.model_validate(row, from_attributes=True)
            for row in self.session.scalars(
                select(ProviderExecutionRow)
                .where(ProviderExecutionRow.run_id == run_id)
                .order_by(ProviderExecutionRow.started_at, ProviderExecutionRow.id)
            )
        )
