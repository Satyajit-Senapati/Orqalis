from typing import cast
from uuid import uuid4

from sqlalchemy import Table, create_engine
from sqlalchemy.orm import Session

from orqalis.domain.approval import (
    ApprovalDecision,
    ApprovalDecisionKind,
    ApprovalRequest,
    ApprovalStage,
    ApprovalStatus,
    ControlMode,
    ControlPolicy,
)
from orqalis.persistence.approval_models import (
    ApprovalDecisionRow,
    ApprovalRequestRow,
    ControlPolicyRow,
)
from orqalis.persistence.approvals import SQLApprovalRepository
from orqalis.persistence.schema import Base


def test_approval_records_survive_new_sessions_and_decisions_are_separate() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=cast(
            list[Table],
            [
                ControlPolicyRow.__table__,
                ApprovalRequestRow.__table__,
                ApprovalDecisionRow.__table__,
            ],
        ),
    )
    run_id = uuid4()
    policy = ControlPolicy(
        run_id=run_id,
        mode=ControlMode.SUPERVISED,
        gates=frozenset({ApprovalStage.GOAL, ApprovalStage.PLAN}),
    )
    request = ApprovalRequest(
        run_id=run_id,
        stage=ApprovalStage.GOAL,
        subject_version=1,
        subject_digest="a" * 64,
    )
    with Session(engine) as session:
        repo = SQLApprovalRepository(session)
        repo.save_policy(policy)
        repo.add_request(request)
        session.commit()

    with Session(engine) as session:
        repo = SQLApprovalRepository(session)
        assert repo.policy(run_id) == policy
        pending = repo.get(request.id)
        assert pending and pending.status == ApprovalStatus.PENDING
        assert repo.list(run_id) == (pending,)
        repo.add_decision(
            ApprovalDecision(
                request_id=request.id,
                decision=ApprovalDecisionKind.APPROVE,
                actor="local-operator",
            )
        )
        session.commit()

    with Session(engine) as session:
        decided = SQLApprovalRepository(session).get(request.id)
        assert decided and decided.status == ApprovalStatus.APPROVED
        assert decided.decision and decided.decision.actor == "local-operator"
        assert session.get(ApprovalRequestRow, request.id) is not None
        assert session.query(ApprovalDecisionRow).filter_by(request_id=request.id).count() == 1
