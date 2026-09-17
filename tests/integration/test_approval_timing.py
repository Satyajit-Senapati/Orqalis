from pathlib import Path

from orqalis.core.approval_subjects import goal_subject
from orqalis.core.approvals import ApprovalService
from orqalis.core.goals import GoalService
from orqalis.core.orchestrator import Orchestrator
from orqalis.core.projects import ProjectService
from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.agent import ActorStatus, ActorType
from orqalis.domain.approval import ApprovalDecisionKind, ApprovalStage, ApprovalStatus, ControlMode
from orqalis.domain.run import RunState
from orqalis.git.service import LocalGitService
from tests.support.filesystem import filesystem_uow_factory


def test_operator_checkpoint_persists_orchestrator_status_and_resumes_on_transition(
    git_repo: Path,
) -> None:
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
    goals, approvals = GoalService(factory), ApprovalService(factory)
    run, goal = goals.create(
        project,
        "Check fixture",
        "feature/test",
        git.status(git_repo).head,
        draft,
        mode=ControlMode.SUPERVISED,
    )
    # The policy and run must be visible together after one creation commit.
    assert approvals.policy(run.id).requires(ApprovalStage.GOAL)
    digest = goal_subject(goal)
    pending = approvals.ensure(run.id, ApprovalStage.GOAL, 1, digest)
    assert pending and pending.status == ApprovalStatus.PENDING

    def actor_status() -> ActorStatus:
        with factory() as uow:
            return next(
                actor.status
                for actor in uow.runtime.actors(run.id)
                if actor.actor_type == ActorType.ORCHESTRATOR
            )

    assert actor_status() == ActorStatus.WAITING_FOR_DEPENDENCY
    approvals.decide(run.id, pending.id, ApprovalDecisionKind.APPROVE, "operator", digest)
    assert actor_status() == ActorStatus.WAITING_FOR_DEPENDENCY
    Orchestrator(factory).advance(run.id, RunState.CONTEXT_SYNC, "context")
    assert actor_status() == ActorStatus.WORKING

    rejected_run, rejected_goal = goals.create(
        project,
        "Check fixture again",
        "feature/second",
        git.status(git_repo).head,
        draft,
        mode=ControlMode.SUPERVISED,
    )
    rejected_digest = goal_subject(rejected_goal)
    rejected_request = approvals.ensure(rejected_run.id, ApprovalStage.GOAL, 1, rejected_digest)
    assert rejected_request
    approvals.decide(
        rejected_run.id,
        rejected_request.id,
        ApprovalDecisionKind.REJECT,
        "operator",
        rejected_digest,
        "Goal needs revision",
    )
    with factory() as uow:
        rejected_actor = next(
            actor
            for actor in uow.runtime.actors(rejected_run.id)
            if actor.actor_type == ActorType.ORCHESTRATOR
        )
        assert rejected_actor.status == ActorStatus.BLOCKED
