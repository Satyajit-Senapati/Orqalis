"""SQL adapter for run control policies and operator decisions."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from orqalis.domain.approval import (
    ApprovalDecision,
    ApprovalDecisionKind,
    ApprovalRequest,
    ApprovalStatus,
    ControlPolicy,
)
from orqalis.persistence.approval_models import (
    ApprovalDecisionRow,
    ApprovalRequestRow,
    ControlPolicyRow,
)


class SQLApprovalRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def policy(self, run_id: UUID) -> ControlPolicy | None:
        row = self.session.get(ControlPolicyRow, run_id)
        return (
            ControlPolicy(run_id=row.run_id, mode=row.mode, gates=frozenset(row.gates))
            if row
            else None
        )

    def save_policy(self, policy: ControlPolicy) -> None:
        row = self.session.get(ControlPolicyRow, policy.run_id)
        if row is None:
            row = ControlPolicyRow(run_id=policy.run_id, mode=policy.mode, gates=[])
            self.session.add(row)
        row.mode = policy.mode
        row.gates = sorted(stage.value for stage in policy.gates)
        self.session.flush()

    def _request(self, row: ApprovalRequestRow) -> ApprovalRequest:
        decision_row = self.session.scalar(
            select(ApprovalDecisionRow).where(ApprovalDecisionRow.request_id == row.id)
        )
        decision = (
            ApprovalDecision(
                id=decision_row.id,
                request_id=decision_row.request_id,
                decision=decision_row.decision,
                actor=decision_row.actor,
                reason=decision_row.reason,
                created_at=_aware_utc(decision_row.created_at),
            )
            if decision_row
            else None
        )
        status = ApprovalStatus.PENDING
        if decision:
            status = (
                ApprovalStatus.APPROVED
                if decision.decision == ApprovalDecisionKind.APPROVE
                else ApprovalStatus.REJECTED
            )
        return ApprovalRequest(
            id=row.id,
            run_id=row.run_id,
            stage=row.stage,
            subject_version=row.subject_version,
            subject_digest=row.subject_digest,
            reason=row.reason,
            status=status,
            decision=decision,
            created_at=_aware_utc(row.created_at),
        )

    def get(self, request_id: UUID) -> ApprovalRequest | None:
        row = self.session.get(ApprovalRequestRow, request_id)
        return self._request(row) if row else None

    def list(self, run_id: UUID) -> tuple[ApprovalRequest, ...]:
        rows = self.session.scalars(
            select(ApprovalRequestRow)
            .where(ApprovalRequestRow.run_id == run_id)
            .order_by(ApprovalRequestRow.created_at, ApprovalRequestRow.id)
        )
        return tuple(self._request(row) for row in rows)

    def add_request(self, request: ApprovalRequest) -> None:
        self.session.add(ApprovalRequestRow(**request.model_dump(exclude={"status", "decision"})))
        self.session.flush()

    def add_decision(self, decision: ApprovalDecision) -> None:
        self.session.add(ApprovalDecisionRow(**decision.model_dump()))
        self.session.flush()


def _aware_utc(value: datetime) -> datetime:
    """SQLite drops timezone data; PostgreSQL retains it."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
