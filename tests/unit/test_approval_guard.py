from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from orqalis.core.approval_guard import require_approval
from orqalis.domain.approval import (
    ApprovalRequest,
    ApprovalStage,
    ApprovalStatus,
    ControlMode,
    ControlPolicy,
)
from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.run import Run


def test_authoritative_guard_persists_pending_then_requires_exact_approval() -> None:
    run = Run(
        project_id=uuid4(),
        request="Validate change",
        target_branch="feature/control",
        base_commit="a" * 40,
        plan_version=1,
    )
    uow: Any = MagicMock()
    uow.approvals.policy.return_value = ControlPolicy(
        run_id=run.id,
        mode=ControlMode.SUPERVISED,
        gates=frozenset({ApprovalStage.PLAN}),
    )
    requests: dict[UUID, ApprovalRequest] = {}
    uow.approvals.get.side_effect = requests.get

    def add_request(request: ApprovalRequest) -> None:
        requests[request.id] = request

    uow.approvals.add_request.side_effect = add_request
    with pytest.raises(PolicyDeniedError, match="PLAN approval required"):
        require_approval(uow, run, ApprovalStage.PLAN, 1, "a" * 64, "Review plan")
    assert len(requests) == 1
    uow.commit.assert_called_once()
    with pytest.raises(PolicyDeniedError):
        require_approval(uow, run, ApprovalStage.PLAN, 1, "a" * 64, "Review plan")
    assert len(requests) == 1
    request = next(iter(requests.values()))
    requests[request.id] = request.model_copy(update={"status": ApprovalStatus.APPROVED})
    require_approval(uow, run, ApprovalStage.PLAN, 1, "a" * 64, "Review plan")
    with pytest.raises(PolicyDeniedError):
        require_approval(uow, run, ApprovalStage.PLAN, 1, "b" * 64, "Changed plan")
