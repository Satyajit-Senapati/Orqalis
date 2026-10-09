from collections.abc import Callable, Iterable
from pathlib import Path
from types import ModuleType

import pytest

import orqalis.core.orchestrator as orchestrator_module
import orqalis.core.preview_revision as preview_revision_module
from orqalis.core.approvals import ApprovalService, prepare_approval_request
from orqalis.core.plan_preview import PlanPreviewService
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.vertical_plan import VerticalPlanner
from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.approval import (
    ApprovalDecisionKind,
    ApprovalRequest,
    ApprovalStage,
    ControlMode,
)
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.domain.events import Event, EventType
from orqalis.domain.projections import RunSnapshot
from orqalis.domain.run import Run, RunState
from orqalis.domain.task import TaskStatus
from orqalis.sdk import Orqalis
from tests.support.filesystem import filesystem_uow_factory


def _prepared(git_repo: Path) -> tuple[Orqalis, PlanPreviewService, RunSnapshot]:
    sdk = Orqalis(unit_of_work=filesystem_uow_factory(git_repo))
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


def test_preview_and_operator_edit_preserve_versions_and_events(git_repo: Path) -> None:
    sdk, service, state = _prepared(git_repo)
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
    git_repo: Path, commit_all: Callable[[Path], str]
) -> None:
    sdk, service, state = _prepared(git_repo)
    (git_repo / "main.py").write_text("answer = 43\n", encoding="utf-8")
    commit_all(git_repo)
    plan = service.preview(state.run.id, "preview")
    assert plan.version == 1
    assert sdk.snapshot(state.run.id).run.state == RunState.PLANNED
    with sdk.unit_of_work() as uow:
        assert uow.execution.workspace(state.run.id) is None


def test_supervised_preview_waits_for_exact_goal_approval(git_repo: Path) -> None:
    sdk, _, state = _prepared(git_repo)
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


def test_preview_recovers_plan_installed_with_a_different_command_key(git_repo: Path) -> None:
    sdk, service, state = _prepared(git_repo)
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


def test_plan_checkpoint_notifications_include_matching_approval(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared, _, state = _prepared(git_repo)
    prepared.close()
    sdk = Orqalis(root=git_repo)
    assert state.goal is not None
    approvals = ApprovalService(sdk.unit_of_work)
    approvals.configure(
        state.run.id, ControlMode.SUPERVISED, frozenset({ApprovalStage.GOAL, ApprovalStage.PLAN})
    )
    service = PlanPreviewService(
        sdk.unit_of_work, sdk.orchestrator, sdk.goals, sdk.memory, sdk.git, approvals
    )
    with pytest.raises(PolicyDeniedError):
        service.preview(state.run.id, "goal-gate")
    goal_request = approvals.list(state.run.id)[-1]
    approvals.decide(
        state.run.id,
        goal_request.id,
        ApprovalDecisionKind.APPROVE,
        "fixture-operator",
        goal_request.subject_digest,
    )
    native_publish = sdk.event_bus.publish
    observed_versions: list[int] = []

    def observe_commit(events: Iterable[Event]) -> None:
        batch = tuple(events)
        if any(
            event.event_type == EventType.PLAN_REVISED
            or event.event_type == EventType.RUN_STATE_CHANGED
            and event.payload.status == RunState.PLANNED
            for event in batch
        ):
            snapshot = sdk.snapshot(state.run.id)
            requests = approvals.list(state.run.id)
            assert snapshot.plan is not None
            assert requests[-1].stage == ApprovalStage.PLAN
            assert requests[-1].subject_version == snapshot.run.plan_version
            assert requests[-1].status == "PENDING"
            assert any(
                event.event_type == EventType.APPROVAL_REQUESTED
                and event.payload.approval_request_id == requests[-1].id
                for event in batch
            )
            observed_versions.append(snapshot.run.plan_version)
        native_publish(batch)

    monkeypatch.setattr(sdk.event_bus, "publish", observe_commit)
    first = service.preview(state.run.id, "atomic-preview")
    edited = VerticalPlanner().plan(
        state.goal,
        sdk.memory.context(sdk.get_project(state.run.project_id), state.run.request),
        version=2,
    )
    second = service.replace(edited, first.version, "atomic-edit")
    before = sdk.events(state.run.id)
    assert service.preview(state.run.id, "atomic-preview") == second
    assert service.replace(edited, first.version, "atomic-edit") == second
    assert sdk.events(state.run.id) == before
    assert observed_versions == [1, 2]
    assert sum(request.stage == ApprovalStage.PLAN for request in approvals.list(state.run.id)) == 2


@pytest.mark.parametrize("checkpoint", ["preview", "replace"])
def test_plan_checkpoint_rolls_back_with_its_approval(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, checkpoint: str
) -> None:
    prepared, _, state = _prepared(git_repo)
    prepared.close()
    sdk = Orqalis(root=git_repo)
    assert state.goal is not None
    approvals = ApprovalService(sdk.unit_of_work)
    approvals.configure(
        state.run.id, ControlMode.SUPERVISED, frozenset({ApprovalStage.GOAL, ApprovalStage.PLAN})
    )
    service = PlanPreviewService(
        sdk.unit_of_work, sdk.orchestrator, sdk.goals, sdk.memory, sdk.git, approvals
    )
    with pytest.raises(PolicyDeniedError):
        service.preview(state.run.id, "goal-gate")
    goal_request = approvals.list(state.run.id)[-1]
    approvals.decide(
        state.run.id,
        goal_request.id,
        ApprovalDecisionKind.APPROVE,
        "fixture-operator",
        goal_request.subject_digest,
    )
    context = sdk.memory.context(sdk.get_project(state.run.project_id), state.run.request)
    plan = VerticalPlanner().plan(state.goal, context)
    component: ModuleType
    if checkpoint == "preview":
        # The recoverable installed-plan checkpoint remains separate by design.
        sdk.orchestrator.install_plan(plan, "installed")
        component = orchestrator_module
        version = 1
    else:
        service.preview(state.run.id, "installed")
        component = preview_revision_module
        version = 2
        plan = VerticalPlanner().plan(state.goal, context, version=version)
    before = sdk.snapshot(state.run.id)
    before_events = sdk.events(state.run.id)
    before_requests = approvals.list(state.run.id)
    native_prepare = prepare_approval_request

    def interrupt_after_staging(
        uow: ProjectUnitOfWork,
        run: Run,
        stage: ApprovalStage,
        subject_version: int,
        subject_digest: str,
        reason: str = "",
    ) -> tuple[ApprovalRequest | None, bool]:
        request, created = native_prepare(uow, run, stage, subject_version, subject_digest, reason)
        assert created and request is not None
        assert request.stage == ApprovalStage.PLAN and request.subject_version == version
        raise RuntimeError("Interrupted before checkpoint commit")

    monkeypatch.setattr(component, "prepare_approval_request", interrupt_after_staging)
    with pytest.raises(RuntimeError, match="Interrupted before checkpoint commit"):
        if checkpoint == "preview":
            service.preview(state.run.id, "interrupted")
        else:
            service.replace(plan, 1, "interrupted")
    after = sdk.snapshot(state.run.id)
    assert after.run == before.run and after.plan == before.plan
    assert sdk.events(state.run.id) == before_events
    assert approvals.list(state.run.id) == before_requests
