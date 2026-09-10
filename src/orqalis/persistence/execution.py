from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from orqalis.domain.execution import ReviewRecord, RunWorkspace, ToolInvocation
from orqalis.persistence.execution_models import ReviewRow, ToolInvocationRow, WorkspaceRow


class SQLExecutionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def try_run_lock(self, run_id: UUID) -> bool:
        # Held by the driver UoW, separate from short state/event transactions.
        key = int.from_bytes(run_id.bytes[:8], byteorder="big", signed=True)
        return bool(
            self.session.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key})
        )

    def workspace(self, run_id: UUID) -> RunWorkspace | None:
        row = self.session.get(WorkspaceRow, run_id)
        return RunWorkspace.model_validate(row, from_attributes=True) if row else None

    def save_workspace(self, workspace: RunWorkspace) -> None:
        self.session.merge(
            WorkspaceRow(
                run_id=workspace.run_id,
                path=str(workspace.path),
                base_commit=workspace.base_commit,
                branch=workspace.branch,
                policy=workspace.policy.model_dump(mode="json"),
            )
        )
        self.session.flush()

    def tool(self, invocation_id: UUID) -> ToolInvocation | None:
        row = self.session.get(ToolInvocationRow, invocation_id)
        return ToolInvocation.model_validate(row, from_attributes=True) if row else None

    def save_tool(self, invocation: ToolInvocation) -> None:
        self.session.merge(
            ToolInvocationRow(
                **invocation.model_dump(exclude={"observation"}),
                observation=invocation.observation.model_dump(mode="json")
                if invocation.observation
                else None,
            )
        )
        self.session.flush()

    def tools(self, run_id: UUID) -> tuple[ToolInvocation, ...]:
        return tuple(
            ToolInvocation.model_validate(row, from_attributes=True)
            for row in self.session.scalars(
                select(ToolInvocationRow)
                .where(ToolInvocationRow.run_id == run_id)
                .order_by(ToolInvocationRow.started_at, ToolInvocationRow.id)
            )
        )

    def save_review(self, review: ReviewRecord) -> None:
        self.session.add(
            ReviewRow(
                **review.model_dump(exclude={"result"}),
                result=review.result.model_dump(mode="json"),
            )
        )
        self.session.flush()

    def reviews(self, run_id: UUID) -> tuple[ReviewRecord, ...]:
        return tuple(
            ReviewRecord.model_validate(row, from_attributes=True)
            for row in self.session.scalars(
                select(ReviewRow)
                .where(ReviewRow.run_id == run_id)
                .order_by(ReviewRow.created_at, ReviewRow.id)
            )
        )
