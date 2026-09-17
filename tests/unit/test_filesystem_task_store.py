from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

from orqalis.core.goals import GoalService
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.domain.acceptance import (
    AcceptanceStatus,
    CriterionDefinition,
    FileValidation,
    GoalContract,
    GoalDraft,
)
from orqalis.domain.agent import ActorSession, ActorStatus, ActorType
from orqalis.domain.approval import (
    ApprovalDecision,
    ApprovalDecisionKind,
    ApprovalRequest,
    ApprovalStage,
    ApprovalStatus,
    ControlMode,
)
from orqalis.domain.artifact import Evidence, ValidationObservation
from orqalis.domain.errors import ConflictError
from orqalis.domain.events import Event, EventDraft, EventPayload, EventType
from orqalis.domain.plan import TaskPlan
from orqalis.domain.project import Project
from orqalis.domain.run import Run
from orqalis.domain.task import Task, TaskExecution, TaskStatus
from orqalis.domain.timing import PhaseExecution
from orqalis.persistence.filesystem.io import read_json_object, read_jsonl
from orqalis.persistence.filesystem.task_store import TaskCapsuleStore, _relative_target


def project_store(root: Path) -> tuple[TaskCapsuleStore, Project]:
    root.mkdir(exist_ok=True)
    store = TaskCapsuleStore.from_root(root)
    project = Project(name="fixture", repo_root=root, default_branch="main")
    with store.unit_of_work() as uow:
        assert uow.projects.add(project) == project
        uow.commit()
    return store, project


def goal_draft() -> GoalDraft:
    return GoalDraft(
        goal="Persist one local task",
        scope=("main.py",),
        definition_of_done=("The task can be resumed from files",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="main.py exists",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    )


def create_run(store: TaskCapsuleStore, project: Project) -> tuple[Run, GoalContract]:
    unit_of_work = cast(Callable[[], ProjectUnitOfWork], store.unit_of_work)
    return GoalService(unit_of_work).create(
        project,
        "Persist local task state",
        "feature/local-task",
        "a" * 40,
        goal_draft(),
        ControlMode.SUPERVISED,
    )


def test_task_capsule_creation_roundtrip_and_index_rebuild(tmp_path: Path) -> None:
    store, project = project_store(tmp_path / "repo")
    run, contract = create_run(store, project)

    capsule_id = store.capsule_id(run.id)
    assert capsule_id is not None and capsule_id.startswith("ORQ-")
    capsule = store.layout.task(capsule_id)
    assert (capsule / "request.md").read_text(encoding="utf-8") == ("Persist local task state\n")
    assert (capsule / "task.yaml").is_file()
    assert (capsule / "goal" / "goal.md").is_file()
    assert (capsule / "goal" / "acceptance.yaml").is_file()
    assert (capsule / "execution" / "state.yaml").is_file()
    assert (capsule / "execution" / "approvals.yaml").is_file()
    events = read_jsonl(capsule / "execution" / "events.jsonl")
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))

    task_document = read_json_object(capsule / "task.yaml")
    assert task_document["run_id"] == str(run.id)
    assert task_document["project"]["starting_commit"] == "a" * 40  # type: ignore[index]
    identity = read_json_object(store.layout.project / "identity.yaml")
    assert identity["repo_root"] == "."
    assert str(tmp_path) not in (store.layout.project / "identity.yaml").read_text()

    with store.unit_of_work() as uow:
        loaded = uow.runs.get(run.id)
        assert loaded is not None
        assert loaded.current_goal_version_id == contract.goal.id
        assert uow.runs.get_goal(contract.goal.id) == contract
        assert uow.approvals.policy(run.id) is not None
        assert uow.projects.get(project.id) == project

    (store.layout.tasks / "index.json").unlink()
    restarted = TaskCapsuleStore.from_root(store.root)
    assert restarted.capsule_id(run.id) == capsule_id
    assert restarted.rebuild_index() == 1
    with restarted.unit_of_work() as uow:
        assert uow.runs.list(project.id) == (uow.runs.get(run.id),)


def test_transaction_recovery_rejects_windows_separator_escape(tmp_path: Path) -> None:
    store, project = project_store(tmp_path / "repo")
    run, _ = create_run(store, project)
    capsule_id = store.capsule_id(run.id)
    assert capsule_id is not None
    capsule = store.layout.task(capsule_id)

    with pytest.raises(ConflictError, match="unsafe target"):
        _relative_target(capsule, r"..\..\escaped.txt")
    assert not (store.root / "escaped.txt").exists()


def test_runtime_goal_evidence_and_approvals_roundtrip(tmp_path: Path) -> None:
    store, project = project_store(tmp_path / "repo")
    run, contract = create_run(store, project)
    task = Task(
        run_id=run.id,
        description="Implement the change",
        expected_outcome="Implementation exists",
        validation_method="file",
        acceptance_criterion_ids=(contract.criteria[0].id,),
    )
    plan = TaskPlan(
        run_id=run.id,
        goal_version_id=contract.goal.id,
        version=1,
        tasks=(task,),
    )
    actor = ActorSession(
        run_id=run.id,
        actor_type=ActorType.AGENT,
        status=ActorStatus.WORKING,
        current_task_id=task.id,
    )
    execution = TaskExecution(
        run_id=run.id,
        task_id=task.id,
        attempt=1,
        assigned_actor_session_id=actor.id,
        status=TaskStatus.RUNNING,
    )
    phase = PhaseExecution(run_id=run.id, phase="IMPLEMENT", started_at=run.created_at)
    evidence = Evidence(
        run_id=run.id,
        criterion_id=contract.criteria[0].id,
        task_id=task.id,
        task_execution_id=execution.id,
        evidence_type="file",
        structured_data=ValidationObservation(
            validator_type="file", passed=True, source_ref="main.py", duration_ms=1
        ),
    )
    criterion = contract.criteria[0].model_copy(
        update={"status": AcceptanceStatus.PASS, "evidence_refs": (evidence.id,)}
    )
    request = ApprovalRequest(
        run_id=run.id,
        stage=ApprovalStage.PLAN,
        subject_version=1,
        subject_digest="b" * 64,
    )
    decision = ApprovalDecision(
        request_id=request.id,
        decision=ApprovalDecisionKind.APPROVE,
        actor="operator",
    )

    with store.unit_of_work() as uow:
        uow.runtime.save_plan(plan)
        uow.runtime.save_actor(actor)
        uow.runtime.save_execution(execution)
        uow.runtime.save_phase(phase)
        uow.runs.save_evaluation(criterion, evidence)
        uow.approvals.add_request(request)
        uow.approvals.add_decision(decision)
        uow.commit()

    with TaskCapsuleStore.from_root(store.root).unit_of_work() as uow:
        loaded_plan = uow.runtime.get_plan(run.id, 1)
        assert loaded_plan is not None and loaded_plan.tasks == (task,)
        assert uow.runtime.tasks(run.id) == (task,)
        assert actor in uow.runtime.actors(run.id)
        assert uow.runtime.executions(run.id) == (execution,)
        assert uow.runtime.phases(run.id) == (phase,)
        assert uow.runs.get_evidence(evidence.id) == evidence
        loaded_goal = uow.runs.get_goal(contract.goal.id)
        assert loaded_goal is not None
        assert loaded_goal.criteria[0] == criterion
        approval = uow.approvals.get(request.id)
        assert approval is not None
        assert approval.status == ApprovalStatus.APPROVED
        assert approval.decision == decision

    capsule_id = store.capsule_id(run.id)
    assert capsule_id is not None
    capsule = store.layout.task(capsule_id)
    assert (capsule / "plan" / "dag.json").is_file()
    assert (capsule / "plan" / "subtasks.yaml").is_file()
    assert (capsule / "evidence" / f"{evidence.id}.json").is_file()


def test_events_are_concurrent_contiguous_idempotent_and_secret_safe(tmp_path: Path) -> None:
    store, project = project_store(tmp_path / "repo")
    run, _ = create_run(store, project)
    initial = len(_events(store, run.id))

    def append(number: int) -> int:
        with store.unit_of_work() as uow:
            event = uow.events.append(
                run.id,
                EventDraft(
                    event_type=EventType.PLAN_REVISED,
                    occurred_at=run.created_at,
                    idempotency_key=f"parallel:{number}",
                    payload=EventPayload(plan_version=number + 1),
                ),
            )
            uow.commit()
            return event.sequence

    with ThreadPoolExecutor(max_workers=4) as pool:
        sequences = list(pool.map(append, range(8)))
    assert len(set(sequences)) == 8
    events = _events(store, run.id)
    assert [item.sequence for item in events] == list(range(1, len(events) + 1))
    assert len(events) == initial + 8
    assert append(0) == next(
        item.sequence for item in events if item.idempotency_key == "parallel:0"
    )

    with store.unit_of_work() as uow:
        with pytest.raises(ConflictError, match="Idempotency"):
            uow.events.append(
                run.id,
                EventDraft(
                    event_type=EventType.PLAN_REVISED,
                    occurred_at=run.created_at,
                    idempotency_key="parallel:0",
                    payload=EventPayload(plan_version=999),
                ),
            )
        with pytest.raises(ConflictError, match="Unsafe"):
            uow.events.append(
                run.id,
                EventDraft(
                    event_type=EventType.PLAN_REVISED,
                    occurred_at=run.created_at,
                    idempotency_key="unsafe",
                    payload=EventPayload(summary="password=do-not-store-this"),
                ),
            )
        uow.rollback()
    assert len(_events(store, run.id)) == initial + 8


def test_rollback_removes_uncommitted_capsule_and_extensions_persist(tmp_path: Path) -> None:
    store, project = project_store(tmp_path / "repo")
    run = Run(
        project_id=project.id,
        request="Do not commit this task",
        target_branch="feature/rollback",
        base_commit="c" * 40,
    )
    with store.unit_of_work() as uow:
        uow.runs.add(run)
        uow.rollback()
    assert store.capsule_id(run.id) is None
    assert not tuple(store.layout.tasks.glob("ORQ-*"))

    committed, _ = create_run(store, project)
    with store.unit_of_work() as uow:
        uow.session.save_extension(committed.id, "delivery", {"commit": "d" * 40})
        uow.session.save_project_extension("memory", {"indexed_commit": "e" * 40})
        uow.commit()
    with TaskCapsuleStore.from_root(store.root).unit_of_work() as uow:
        assert uow.session.extension(committed.id, "delivery") == {"commit": "d" * 40}
        assert uow.session.project_extension("memory") == {"indexed_commit": "e" * 40}


def test_two_project_roots_are_isolated(tmp_path: Path) -> None:
    store_a, project_a = project_store(tmp_path / "repo-a")
    store_b, project_b = project_store(tmp_path / "repo-b")
    run_a, _ = create_run(store_a, project_a)
    run_b, _ = create_run(store_b, project_b)

    assert store_a.capsule_id(run_a.id) is not None
    assert store_a.capsule_id(run_b.id) is None
    assert store_b.capsule_id(run_b.id) is not None
    assert store_b.capsule_id(run_a.id) is None
    with store_a.unit_of_work() as uow:
        assert uow.runs.get(run_b.id) is None
        assert uow.runs.list(project_b.id) == ()


def test_controller_lease_is_exclusive_between_units_of_work(tmp_path: Path) -> None:
    store, project = project_store(tmp_path / "repo")
    run, _ = create_run(store, project)

    with store.unit_of_work() as holder:
        assert holder.session.try_run_lock(run.id)
        with store.unit_of_work() as competitor:
            assert not competitor.session.try_run_lock(run.id)

    with store.unit_of_work() as successor:
        assert successor.session.try_run_lock(run.id)


def _events(store: TaskCapsuleStore, run_id: UUID) -> tuple[Event, ...]:
    with store.unit_of_work() as uow:
        return uow.events.list(run_id)
