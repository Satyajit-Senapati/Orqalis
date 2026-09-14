from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy import Engine

from orqalis.core.approvals import ApprovalService
from orqalis.core.plan_preview import PlanPreviewService
from orqalis.core.vertical_plan import VerticalPlanner
from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.approval import ApprovalDecisionKind, ApprovalStage, ControlMode
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.domain.events import EventType
from orqalis.domain.projections import RunSnapshot
from orqalis.domain.run import RunState
from orqalis.domain.task import TaskStatus
from orqalis.persistence.database import session_factory
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork
from orqalis.sdk import Orqalis

pytestmark = pytest.mark.postgres


def _prepared(database: Engine, git_repo: Path) -> tuple[Orqalis, PlanPreviewService, RunSnapshot]:
    sdk = Orqalis(unit_of_work=lambda: SQLProjectUnitOfWork(session_factory(database)))
    project = sdk.initialize(git_repo)
    draft = GoalDraft(
        goal="Update the fixture source",
        scope=("main.py",),
        definition_of_done=("Source file exists",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="Source file exists",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    )
    state = sdk.prepare_run(project.id, "Update the fixture source", "feature/preview", draft)
    assert state.run.state == RunState.GOAL_DEFINED
    assert state.goal is not None
    return (
        sdk,
        PlanPreviewService(sdk.unit_of_work, sdk.orchestrator, sdk.goals, sdk.memory, sdk.git),
        state,
    )


def test_preview_and_operator_edit_preserve_versions_and_events(
    database: Engine, git_repo: Path
) -> None:
    sdk, service, state = _prepared(database, git_repo)
    run_id = state.run.id
    assert state.goal is not None
    original = service.preview(run_id, "preview")
    assert original.version == 1
    assert sdk.snapshot(run_id).run.state == RunState.PLANNED
    with sdk.unit_of_work() as uow:
        assert uow.execution.workspace(run_id) is None
        before = uow.events.list(run_id)
    assert service.preview(run_id, "preview") == original
    assert sdk.events(run_id) == before

    edited = VerticalPlanner().plan(
        state.goal,
        sdk.memory.context(sdk.get_project(state.run.project_id), state.run.request),
        version=2,
    )
    tasks = (
        edited.tasks[0].model_copy(update={"description": "Change main.py only"}),
        *edited.tasks[1:],
    )
    edited = edited.model_copy(update={"tasks": tasks})
    replacement = service.replace(edited, 1, "edit")
    assert replacement.version == 2
    assert any(task.description == "Change main.py only" for task in replacement.tasks)
    assert service.replace(edited, 1, "edit") == replacement
    with sdk.unit_of_work() as uow:
        previous = uow.runtime.get_plan(run_id, 1)
        current = uow.runtime.get_plan(run_id, 2)
        assert previous and current
        assert all(task.status == TaskStatus.CANCELLED for task in previous.tasks)
        assert any(task.status == TaskStatus.READY for task in current.tasks)
        updated = uow.runs.get(run_id)
        assert updated is not None and updated.plan_version == 2
        kinds = [event.event_type for event in uow.events.list(run_id)]
        assert kinds.count(EventType.PLAN_CREATED) == 1
        assert kinds.count(EventType.PLAN_REVISED) == 1
    with pytest.raises(ConflictError, match="stale expected version"):
        service.replace(
            VerticalPlanner().plan(
                state.goal,
                sdk.memory.context(sdk.get_project(state.run.project_id), state.run.request),
                version=2,
            ),
            1,
            "stale",
        )
    sdk.orchestrator.advance(run_id, RunState.EXECUTING, "execute")
    with pytest.raises(ConflictError, match="unexecuted PLANNED"):
        service.replace(edited, 2, "late")


def test_preview_uses_pinned_git_base_after_head_moves(
    database: Engine, git_repo: Path, commit_all: Callable[[Path], str]
) -> None:
    sdk, service, state = _prepared(database, git_repo)
    (git_repo / "main.py").write_text("answer = 43\n", encoding="utf-8")
    commit_all(git_repo)
    plan = service.preview(state.run.id, "preview")
    assert plan.version == 1
    assert sdk.snapshot(state.run.id).run.state == RunState.PLANNED
    with sdk.unit_of_work() as uow:
        assert uow.execution.workspace(state.run.id) is None


def test_supervised_preview_waits_for_exact_goal_approval(database: Engine, git_repo: Path) -> None:
    sdk, _, state = _prepared(database, git_repo)
    approvals = ApprovalService(sdk.unit_of_work)
    approvals.configure(state.run.id, ControlMode.SUPERVISED, frozenset({ApprovalStage.GOAL}))
    service = PlanPreviewService(
        sdk.unit_of_work, sdk.orchestrator, sdk.goals, sdk.memory, sdk.git, approvals
    )
    with pytest.raises(PolicyDeniedError, match="Goal approval required"):
        service.preview(state.run.id, "preview")
    requests = approvals.list(state.run.id)
    assert len(requests) == 1
    assert sdk.snapshot(state.run.id).run.plan_version == 0
    approved = approvals.decide(
        state.run.id,
        requests[0].id,
        ApprovalDecisionKind.APPROVE,
        "fixture-operator",
        requests[0].subject_digest,
    )
    assert approved.status == "APPROVED"
    assert service.preview(state.run.id, "preview").version == 1


def test_preview_recovers_plan_installed_with_a_different_command_key(
    database: Engine, git_repo: Path
) -> None:
    sdk, service, state = _prepared(database, git_repo)
    assert state.goal is not None
    plan = VerticalPlanner().plan(
        state.goal, sdk.memory.context(sdk.get_project(state.run.project_id), state.run.request)
    )
    sdk.orchestrator.install_plan(plan, "first-command")
    assert sdk.snapshot(state.run.id).run.state == RunState.GOAL_DEFINED
    assert sdk.snapshot(state.run.id).run.plan_version == 1
    recovered = service.preview(state.run.id, "new-command")
    assert recovered.version == 1
    assert {task.id for task in recovered.tasks} == {task.id for task in plan.tasks}
    assert sdk.snapshot(state.run.id).run.state == RunState.PLANNED
