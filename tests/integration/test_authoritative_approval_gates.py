from pathlib import Path
from uuid import uuid4

import pytest

from orqalis.core.delivery_plan import delivery_plan
from orqalis.core.vertical_plan import VerticalPlanner
from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.approval import ApprovalDecisionKind, ApprovalStage, ControlMode
from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.run import RunState
from orqalis.sdk import Orqalis


def test_direct_orchestrator_calls_cannot_skip_goal_or_plan_approval(git_repo: Path) -> None:
    sdk = Orqalis(root=git_repo)
    project = sdk.initialize(git_repo)
    goal = GoalDraft(
        goal="Check fixture",
        scope=("main.py",),
        definition_of_done=("File exists",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="File exists",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    )
    state = sdk.prepare_run(
        project.id,
        "Check fixture",
        f"feature/direct-guard-{uuid4().hex[:8]}",
        goal,
        ControlMode.SUPERVISED,
    )
    run_id = state.run.id
    plan = VerticalPlanner().plan(
        sdk.goals.get(run_id), sdk.memory.context(project, state.run.request)
    )
    with pytest.raises(PolicyDeniedError, match="GOAL approval required"):
        sdk.orchestrator.install_plan(plan, "direct")
    goal_request = sdk.approvals.list(run_id)[-1]
    assert goal_request.stage == ApprovalStage.GOAL
    sdk.approvals.decide(
        run_id,
        goal_request.id,
        ApprovalDecisionKind.APPROVE,
        "test-operator",
        goal_request.subject_digest,
    )
    sdk.orchestrator.install_plan(plan, "direct")
    sdk.orchestrator.advance(run_id, RunState.PLANNED, "direct:planned")
    with pytest.raises(PolicyDeniedError, match="PLAN approval required"):
        sdk.orchestrator.advance(run_id, RunState.EXECUTING, "direct:execute")
    plan_request = sdk.approvals.list(run_id)[-1]
    assert plan_request.stage == ApprovalStage.PLAN
    sdk.approvals.decide(
        run_id,
        plan_request.id,
        ApprovalDecisionKind.APPROVE,
        "test-operator",
        plan_request.subject_digest,
    )
    assert (
        sdk.orchestrator.advance(run_id, RunState.EXECUTING, "direct:execute").state
        == RunState.EXECUTING
    )
    sdk.orchestrator.advance(run_id, RunState.INTEGRATING, "direct:integrate")
    sdk.orchestrator.advance(run_id, RunState.TESTING, "direct:test")
    sdk.orchestrator.advance(run_id, RunState.REVIEWING, "direct:review")
    current_plan = sdk.snapshot(run_id).plan
    assert current_plan is not None
    with pytest.raises(PolicyDeniedError, match="passing review"):
        sdk.orchestrator.install_delivery_plan(delivery_plan(current_plan), "direct:delivery")
    assert sdk.snapshot(run_id).run.plan_version == 1
    sdk.orchestrator.advance(run_id, RunState.PAUSED, "direct:pause")
    revised = sdk.goals.revise(run_id, goal, "Review a new contract version", 1)
    next_plan = VerticalPlanner().plan(
        revised, sdk.memory.context(project, state.run.request), version=2
    )
    with pytest.raises(PolicyDeniedError, match="GOAL approval required"):
        sdk.orchestrator.install_revised_goal_plan(next_plan, "direct:replan")
    assert sdk.snapshot(run_id).run.plan_version == 1
