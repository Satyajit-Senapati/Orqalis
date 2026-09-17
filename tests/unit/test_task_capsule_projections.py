from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest

from orqalis.context.models import ProjectContextPack
from orqalis.domain.acceptance import (
    AcceptanceCriterion,
    AcceptanceStatus,
    FileValidation,
    GoalContract,
    GoalVersion,
)
from orqalis.domain.agent import ActorSession, ActorStatus, ActorType, AgentRole
from orqalis.domain.artifact import Artifact, Evidence, Finding, ValidationObservation
from orqalis.domain.delivery import (
    ChangedFile,
    ChangeReport,
    DeliveryPolicy,
    FinalValidation,
    GitDelivery,
)
from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.execution import CriterionReview, ReviewRecord, ReviewResult
from orqalis.domain.plan import TaskPlan
from orqalis.domain.project import Project
from orqalis.domain.run import Run, RunState, UIPhase
from orqalis.domain.task import Task, TaskExecution, TaskStatus
from orqalis.domain.timing import PhaseExecution
from orqalis.persistence.filesystem import TaskCapsuleStore, read_json_object, read_jsonl
from orqalis.persistence.filesystem.unit_of_work import FilesystemProjectUnitOfWork


@dataclass(frozen=True, slots=True)
class ProjectionIds:
    task: UUID
    actor: UUID
    guardian: UUID
    finding: UUID


def _initialized(root: Path) -> tuple[TaskCapsuleStore, Project, Run]:
    root.mkdir()
    store = TaskCapsuleStore.from_root(root)
    project = Project(name="projection-fixture", repo_root=root, default_branch="main")
    run = Run(
        project_id=project.id,
        request="Persist readable Task Capsule projections",
        target_branch="feature/projections",
        base_commit="a" * 40,
    )
    with FilesystemProjectUnitOfWork(store) as uow:
        uow.projects.add(project)
        uow.runs.add(run)
        uow.commit()
    return store, project, run


def _capsule(store: TaskCapsuleStore, run: Run) -> Path:
    capsule_id = store.capsule_id(run.id)
    assert capsule_id is not None
    return store.layout.task(capsule_id)


def _materialize(store: TaskCapsuleStore, project: Project, run: Run) -> ProjectionIds:
    goal = GoalVersion(
        run_id=run.id,
        version=1,
        goal="Persist complete lifecycle projections",
        scope=("main.py",),
        definition_of_done=("Every observed stage has a readable projection",),
    )
    criterion = AcceptanceCriterion(
        goal_version_id=goal.id,
        key="AC-1",
        description="main.py is recorded",
        priority="required",
        validation_spec=FileValidation(path="main.py"),
    )
    contract = GoalContract(goal=goal, criteria=(criterion,))
    task = Task(
        run_id=run.id,
        description="Implement the local projection",
        expected_outcome="Projection files exist",
        status=TaskStatus.SUCCEEDED,
        validation_method="file",
        completed_at=run.created_at,
        acceptance_criterion_ids=(criterion.id,),
    )
    plan = TaskPlan(
        run_id=run.id,
        goal_version_id=goal.id,
        version=1,
        tasks=(task,),
    )
    actor = ActorSession(
        run_id=run.id,
        actor_type=ActorType.AGENT,
        role=AgentRole.DEVELOPER,
        provider="fixture",
        model="fixture-model",
        status=ActorStatus.COMPLETE,
        current_task_id=task.id,
        completed_at=run.created_at,
        tasks_attempted=1,
        tasks_completed=1,
    )
    execution = TaskExecution(
        run_id=run.id,
        task_id=task.id,
        attempt=1,
        assigned_actor_session_id=actor.id,
        status=TaskStatus.SUCCEEDED,
        started_at=run.created_at,
        completed_at=run.created_at,
        active_ms=25,
    )
    phase = PhaseExecution(
        run_id=run.id,
        phase=UIPhase.IMPLEMENT,
        started_at=run.created_at,
        completed_at=run.created_at,
        status=TaskStatus.SUCCEEDED,
        active_ms=25,
    )
    evidence = Evidence(
        run_id=run.id,
        criterion_id=criterion.id,
        task_id=task.id,
        task_execution_id=execution.id,
        evidence_type="file",
        structured_data=ValidationObservation(
            validator_type="file",
            passed=True,
            source_ref="main.py",
            duration_ms=1,
        ),
    )
    passed = criterion.model_copy(
        update={
            "status": AcceptanceStatus.PASS,
            "attempt_count": 1,
            "last_validated_at": run.created_at,
            "evidence_refs": (evidence.id,),
        }
    )
    review = ReviewRecord(
        run_id=run.id,
        goal_version_id=goal.id,
        plan_version=1,
        actor_session_id=actor.id,
        tree_hash="b" * 64,
        result=ReviewResult(
            overall="PASS",
            criteria=(
                CriterionReview(
                    criterion_id=criterion.id,
                    status="PASS",
                    reason="The projected file is present.",
                    evidence_refs=(evidence.id,),
                    source_checks=(),
                ),
            ),
            blocking_findings=(),
            non_blocking_findings=(),
        ),
    )
    finding = Finding(
        run_id=run.id,
        task_id=task.id,
        criterion_id=criterion.id,
        severity="info",
        category="scope",
        summary="Projection scope is correct",
        status="resolved",
    )
    change = ChangedFile(
        path="main.py",
        status="modified",
        old_hash="c" * 64,
        new_hash="d" * 64,
        added_lines=3,
        deleted_lines=1,
        binary=False,
    )
    guardian = ChangeReport(
        run_id=run.id,
        actor_session_id=actor.id,
        checkpoint="final",
        base_commit=run.base_commit,
        tree_hash="e" * 64,
        passed=True,
        changes=(change,),
        findings=(finding,),
    )
    validation = FinalValidation(
        run_id=run.id,
        actor_session_id=actor.id,
        goal_version_id=goal.id,
        tree_hash=guardian.tree_hash,
        passed=True,
        evidence_ids=(evidence.id,),
    )
    artifact = Artifact(
        run_id=run.id,
        task_id=task.id,
        type="report",
        path_or_uri="artifacts/report.json",
        content_hash="f" * 64,
    )
    delivery = GitDelivery(
        run_id=run.id,
        base_commit=run.base_commit,
        branch=run.target_branch,
        tree_hash=guardian.tree_hash,
        git_tree_sha="1" * 40,
        commit_message="Persist readable capsule projections",
        commit_attached=True,
        commit_sha="2" * 40,
        push_status="pushed",
        remote="origin",
        policy=DeliveryPolicy(push=True),
    )
    context = ProjectContextPack(
        task=run.request,
        project_id=str(project.id),
        project_name=project.name,
        branch=run.target_branch,
        head_commit=run.base_commit,
        dirty_paths=("main.py",),
        relevant_files=("main.py",),
        size_chars=256,
        max_chars=2_000,
    )
    completed = run.model_copy(
        update={
            "current_goal_version_id": goal.id,
            "state": RunState.COMPLETED,
            "ui_phase": UIPhase.DELIVER,
            "started_at": run.created_at,
            "completed_at": run.created_at + timedelta(seconds=1),
            "plan_version": 1,
        }
    )

    with FilesystemProjectUnitOfWork(store) as uow:
        uow.runs.save_goal(contract)
        uow.runs.set_current_goal(run.id, goal.id)
        uow.runtime.save_plan(plan)
        uow.runtime.save_actor(actor)
        uow.runtime.save_execution(execution)
        uow.runtime.save_phase(phase)
        uow.runs.save_evaluation(passed, evidence)
        uow.execution.save_review(review)
        uow.delivery.save_guardian(guardian)
        uow.delivery.save_validation(validation)
        uow.delivery.save_artifact(artifact)
        uow.delivery.save(delivery)
        uow.session.save_extension(run.id, "context", context.model_dump(mode="json"))
        uow.runs.save(completed)
        uow.commit()
    return ProjectionIds(task=task.id, actor=actor.id, guardian=guardian.id, finding=finding.id)


def test_stage_projection_files_are_absent_before_state_exists(tmp_path: Path) -> None:
    store, _, run = _initialized(tmp_path / "repo")
    capsule = _capsule(store, run)

    assert not (capsule / "context").exists()
    assert not (capsule / "execution" / "phases").exists()
    assert not (capsule / "execution" / "agents").exists()
    assert not (capsule / "execution" / "subtasks").exists()
    assert not (capsule / "review").exists()
    assert not (capsule / "artifacts").exists()
    assert not (capsule / "changes").exists()
    assert not (capsule / "delivery").exists()
    assert not (capsule / "final").exists()

    with FilesystemProjectUnitOfWork(store) as uow:
        suspended = run.model_copy(
            update={"state": RunState.BLOCKED, "resume_state": RunState.RECEIVED}
        )
        uow.runs.save(suspended)
        uow.commit()
    assert not (capsule / "final").exists()


def test_observed_stages_materialize_human_readable_projections(tmp_path: Path) -> None:
    store, project, run = _initialized(tmp_path / "repo")
    identifiers = _materialize(store, project, run)
    capsule = _capsule(store, run)

    expected = (
        "context/context-pack.md",
        "context/memory-used.yaml",
        "context/files-used.json",
        "context/graph-query.json",
        "execution/phases/implementation.yaml",
        f"execution/agents/{identifiers.actor}/session.yaml",
        f"execution/subtasks/{identifiers.task}.yaml",
        "review/acceptance-results.yaml",
        "review/findings.jsonl",
        "review/change-guardian.yaml",
        "artifacts/index.yaml",
        "changes/files.json",
        "changes/diff-summary.md",
        "delivery/commit.yaml",
        "delivery/push.yaml",
        "final/result.yaml",
        "final/summary.md",
    )
    assert all((capsule / relative).is_file() for relative in expected)
    phase = read_json_object(capsule / "execution" / "phases" / "implementation.yaml")
    projection = cast(dict[str, object], phase["_projection"])
    assert projection == {
        "authoritative": False,
        "generation": 2,
        "source": "execution/state.yaml",
    }
    findings = read_jsonl(capsule / "review" / "findings.jsonl")
    assert findings[0]["id"] == str(identifiers.finding)
    final = read_json_object(capsule / "final" / "result.yaml")
    assert final["state"] == "COMPLETED"
    assert cast(dict[str, object], final["acceptance"])["PASS"] == 1
    summary = (capsule / "final" / "summary.md").read_text(encoding="utf-8")
    assert "not authoritative state" in summary
    assert "State: **COMPLETED**" in summary


def test_restart_ignores_and_regenerates_projection_files(tmp_path: Path) -> None:
    store, project, run = _initialized(tmp_path / "repo")
    identifiers = _materialize(store, project, run)
    capsule = _capsule(store, run)
    guardian_path = capsule / "review" / "change-guardian.yaml"
    guardian_path.write_text("not valid projection data", encoding="utf-8")
    (capsule / "review" / "findings.jsonl").unlink()

    restarted = TaskCapsuleStore.from_root(store.root)
    with FilesystemProjectUnitOfWork(restarted) as uow:
        loaded = uow.runs.get(run.id, for_update=True)
        assert loaded is not None and loaded.state == RunState.COMPLETED
        assert uow.delivery.guardians(run.id)[0].id == identifiers.guardian
        uow.runs.save(loaded)
        uow.commit()

    guardian = read_json_object(guardian_path)
    latest = cast(dict[str, object], guardian["latest"])
    assert latest["id"] == str(identifiers.guardian)
    assert read_jsonl(capsule / "review" / "findings.jsonl")[0]["id"] == str(identifiers.finding)
    state = read_json_object(capsule / "execution" / "state.yaml")
    assert cast(dict[str, object], state["run"])["state"] == "COMPLETED"
    assert project.id == run.project_id


def test_secret_bearing_stage_state_is_denied_before_persistence(tmp_path: Path) -> None:
    store, _, run = _initialized(tmp_path / "repo")
    secret = uuid4().hex
    actor = ActorSession(
        run_id=run.id,
        actor_type=ActorType.AGENT,
        role=AgentRole.DEVELOPER,
        activity_summary=f"password={secret}",
    )

    with FilesystemProjectUnitOfWork(store) as uow:
        uow.runtime.save_actor(actor)
        with pytest.raises(PolicyDeniedError, match="credentials or private data"):
            uow.commit()
        uow.rollback()

    assert all(
        secret.encode() not in path.read_bytes()
        for path in store.layout.store.rglob("*")
        if path.is_file()
    )
    with FilesystemProjectUnitOfWork(TaskCapsuleStore.from_root(store.root)) as uow:
        assert uow.runtime.actors(run.id) == ()
