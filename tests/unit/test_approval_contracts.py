from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest

from orqalis.core.approvals import ApprovalService, fingerprint_subject
from orqalis.domain.approval import (
    SUPERVISED_GATES,
    ApprovalRequest,
    ApprovalStage,
    ControlMode,
    ControlPolicy,
)
from orqalis.domain.errors import NotFoundError


def test_subject_fingerprint_is_canonical_and_policy_is_explicit() -> None:
    assert fingerprint_subject({"a": [1, 2], "b": 3}) == fingerprint_subject({"b": 3, "a": [1, 2]})
    assert fingerprint_subject({"a": [2, 1], "b": 3}) != fingerprint_subject({"a": [1, 2], "b": 3})
    run_id = uuid4()
    assert not ControlPolicy(run_id=run_id).requires(ApprovalStage.GOAL)
    supervised = ControlPolicy(run_id=run_id, mode=ControlMode.SUPERVISED, gates=SUPERVISED_GATES)
    assert supervised.requires(ApprovalStage.GOAL)
    assert not supervised.requires(ApprovalStage.TASK)


def test_fingerprint_normalizes_uuid_subjects() -> None:
    identifier = uuid4()
    assert fingerprint_subject((identifier, {"goal": identifier})) == fingerprint_subject(
        (str(identifier), {"goal": str(identifier)})
    )


@pytest.mark.parametrize("supervised", [False, True])
def test_control_state_uses_one_injected_read_snapshot(supervised: bool) -> None:
    run_id = uuid4()
    request = ApprovalRequest(
        run_id=run_id, stage=ApprovalStage.GOAL, subject_version=1, subject_digest="a" * 64
    )
    policy = (
        ControlPolicy(run_id=run_id, mode=ControlMode.SUPERVISED, gates=SUPERVISED_GATES)
        if supervised
        else None
    )
    uow = MagicMock()
    uow.__enter__.return_value = uow
    uow.runs.get.return_value = object()
    uow.approvals.policy.return_value = policy
    uow.approvals.list.return_value = (request,)
    factory = Mock(return_value=uow)
    state = ApprovalService(factory).control_state(run_id)
    assert state == (policy or ControlPolicy(run_id=run_id), (request,))
    factory.assert_called_once_with()
    uow.runs.get.assert_called_once_with(run_id)
    uow.approvals.policy.assert_called_once_with(run_id)
    uow.approvals.list.assert_called_once_with(run_id)
    uow.commit.assert_not_called()


def test_control_state_missing_run_does_not_read_or_mutate_approvals() -> None:
    uow = MagicMock()
    uow.__enter__.return_value = uow
    uow.runs.get.return_value = None
    factory = Mock(return_value=uow)
    with pytest.raises(NotFoundError, match="Run not found"):
        ApprovalService(factory).control_state(uuid4())
    factory.assert_called_once_with()
    uow.approvals.policy.assert_not_called()
    uow.approvals.list.assert_not_called()
    uow.commit.assert_not_called()
