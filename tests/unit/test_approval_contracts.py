from uuid import uuid4

from orqalis.core.approvals import fingerprint_subject
from orqalis.domain.approval import SUPERVISED_GATES, ApprovalStage, ControlMode, ControlPolicy


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
