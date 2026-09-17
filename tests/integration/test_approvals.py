from pathlib import Path

import pytest

from orqalis.core.approval_subjects import goal_subject
from orqalis.core.approvals import ApprovalService
from orqalis.core.goals import GoalService
from orqalis.core.projects import ProjectService
from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.approval import (
    ApprovalDecisionKind,
    ApprovalStage,
    ApprovalStatus,
    ControlMode,
)
from orqalis.domain.errors import ConflictError, InputError
from orqalis.domain.events import EventType
from orqalis.git.service import LocalGitService
from tests.support.filesystem import filesystem_uow_factory


def test_persisted_operator_decisions_bind_to_goal_version_and_digest(git_repo: Path) -> None:
    factory = filesystem_uow_factory(git_repo)

    git = LocalGitService()
    project = ProjectService(factory, git).initialize(git_repo)
    draft = GoalDraft(
        goal="Check fixture",
        scope=("main.py",),
        definition_of_done=("file exists",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="File exists",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    )
    goals = GoalService(factory)
    run, contract = goals.create(
        project, "Check fixture", "feature/test", git.status(git_repo).head, draft
    )
    service = ApprovalService(factory)
    assert service.policy(run.id).mode == ControlMode.AUTONOMOUS
    assert service.ensure(run.id, ApprovalStage.GOAL, 1, "0" * 64) is None

    configured = service.configure(run.id, ControlMode.SUPERVISED)
    assert configured.requires(ApprovalStage.GOAL)
    assert not configured.requires(ApprovalStage.TASK)
    digest = goal_subject(contract)
    request = service.ensure(run.id, ApprovalStage.GOAL, 1, digest, "Review goal contract")
    assert request and request.status == ApprovalStatus.PENDING
    assert service.ensure(run.id, ApprovalStage.GOAL, 1, digest) == request
    assert service.list(run.id) == (request,)
    with pytest.raises(ConflictError):
        service.decide(run.id, request.id, ApprovalDecisionKind.APPROVE, "operator", "f" * 64)
    with pytest.raises(InputError, match="requires a reason"):
        service.decide(run.id, request.id, ApprovalDecisionKind.REJECT, "operator", digest)
    approved = service.decide(
        run.id, request.id, ApprovalDecisionKind.APPROVE, "operator", digest, "Reviewed"
    )
    assert approved.status == ApprovalStatus.APPROVED
    assert approved.decision and approved.decision.actor == "operator"
    assert (
        service.decide(run.id, request.id, ApprovalDecisionKind.APPROVE, "operator", digest)
        == approved
    )
    with pytest.raises(ConflictError):
        service.decide(
            run.id, request.id, ApprovalDecisionKind.REJECT, "operator", digest, "Not accepted"
        )
    with pytest.raises(ConflictError):
        service.configure(run.id, ControlMode.AUTONOMOUS)

    revised = goals.revise(run.id, draft, "Clarify contract", expected_version=1)
    with pytest.raises(ConflictError):
        service.ensure(run.id, ApprovalStage.GOAL, 1, digest)
    with pytest.raises(ConflictError):
        service.decide(run.id, request.id, ApprovalDecisionKind.APPROVE, "operator", digest)
    next_digest = goal_subject(revised)
    next_request = service.ensure(run.id, ApprovalStage.GOAL, 2, next_digest)
    assert next_request and next_request.id != request.id
    assert next_request.status == ApprovalStatus.PENDING
    with factory() as uow:
        kinds = [event.event_type for event in uow.events.list(run.id)]
    assert kinds.count(EventType.APPROVAL_REQUESTED) == 2
    assert kinds.count(EventType.APPROVAL_RECORDED) == 1
    assert EventType.CONTROL_POLICY_CHANGED in kinds
