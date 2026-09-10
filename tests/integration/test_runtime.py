from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from orqalis.core.goals import GoalService
from orqalis.core.orchestrator import Orchestrator
from orqalis.core.projects import ProjectService
from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.agent import ActorType
from orqalis.domain.errors import ConflictError
from orqalis.domain.events import EventDraft, EventPayload, EventType
from orqalis.domain.plan import TaskPlan
from orqalis.domain.run import RunState
from orqalis.domain.task import Task, TaskDependency, TaskStatus
from orqalis.git.service import LocalGitService
from orqalis.observability.projections import SnapshotProjectionService
from orqalis.persistence.database import session_factory
from orqalis.persistence.runtime_models import EventRow
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork

pytestmark = pytest.mark.postgres


@dataclass
class Clock:
    at: datetime

    def __call__(self) -> datetime:
        return self.at

    def tick(self, seconds: int) -> None:
        self.at += timedelta(seconds=seconds)


def test_durable_task_attempts_pause_resume_cancel_and_timing(
    database: Engine, git_repo: Path
) -> None:
    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    git = LocalGitService()
    project = ProjectService(factory, git).initialize(git_repo)
    draft = GoalDraft(
        goal="Test runtime",
        scope=("main.py",),
        definition_of_done=("criterion passes",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="main exists",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    )
    run, goal = GoalService(factory).create(
        project, "test runtime", "feature/runtime", git.status(git_repo).head, draft
    )
    clock = Clock(run.created_at + timedelta(seconds=1))
    orchestrator = Orchestrator(factory, clock)
    for state in (RunState.CONTEXT_SYNC, RunState.ANALYZING, RunState.GOAL_DEFINED):
        orchestrator.advance(run.id, state, state.value)
        clock.tick(1)
    first = Task(
        run_id=run.id,
        description="implementation",
        expected_outcome="done",
        validation_method="test",
        acceptance_criterion_ids=(goal.criteria[0].id,),
    )
    second = Task(
        run_id=run.id,
        description="dependent",
        expected_outcome="done",
        validation_method="test",
        acceptance_criterion_ids=(goal.criteria[0].id,),
    )
    plan = TaskPlan(
        run_id=run.id,
        goal_version_id=goal.goal.id,
        version=1,
        tasks=(first, second),
        dependencies=(TaskDependency(task_id=second.id, depends_on_task_id=first.id),),
    )
    orchestrator.install_plan(plan, "plan")
    orchestrator.advance(run.id, RunState.PLANNED, "planned")
    orchestrator.advance(run.id, RunState.EXECUTING, "execute")
    with pytest.raises(ConflictError):
        orchestrator.start_task(run.id, second.id, "premature")
    attempt = orchestrator.start_task(run.id, first.id, "first")
    assert orchestrator.start_task(run.id, first.id, "first").id == attempt.id
    with pytest.raises(ConflictError):
        orchestrator.advance(run.id, RunState.PAUSED, "unsafe-pause")
    clock.tick(4)
    orchestrator.transition_task(run.id, attempt.id, TaskStatus.WAITING, "wait")
    clock.tick(3)
    orchestrator.advance(run.id, RunState.PAUSED, "pause")
    clock.tick(2)
    # New service instances reload every authoritative value from PostgreSQL.
    resumed = Orchestrator(factory, clock)
    resumed.resume(run.id, "resume")
    resumed.transition_task(run.id, attempt.id, TaskStatus.RUNNING, "continue")
    clock.tick(5)
    completed = resumed.transition_task(run.id, attempt.id, TaskStatus.SUCCEEDED, "finish")
    assert (completed.active_ms, completed.waiting_ms, completed.blocked_ms) == (9000, 5000, 0)
    snapshot = SnapshotProjectionService(factory, clock).get_snapshot(run.id)
    assert snapshot.plan_completion == 50
    assert snapshot.task_counts[TaskStatus.READY] == 1
    assert snapshot.task_timing[first.id].wall_ms == 14000
    assert snapshot.timing.waiting_ms == 2000
    assert {item.session.actor_type for item in snapshot.actors} == {
        ActorType.ORCHESTRATOR,
        ActorType.AGENT,
    }
    assert snapshot == SnapshotProjectionService(factory, clock).get_snapshot(run.id)
    with factory() as uow:
        events = uow.events.list(run.id)
        assert [event.sequence for event in events] == list(range(1, len(events) + 1))
        assert snapshot.last_event_sequence == events[-1].sequence
        assert uow.events.list(run.id, events[-1].sequence) == ()
    resumed.advance(run.id, RunState.CANCELLED, "cancel")
    cancelled = SnapshotProjectionService(factory, clock).get_snapshot(run.id)
    assert cancelled.run.state == RunState.CANCELLED
    assert cancelled.task_counts[TaskStatus.CANCELLED] == 1
    assert all(item.execution.completed_at for item in cancelled.phases)
    with pytest.raises(ConflictError):
        resumed.advance(run.id, RunState.EXECUTING, "restart")


def test_event_sequence_concurrency_idempotency_and_append_only(
    database: Engine, git_repo: Path
) -> None:
    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    git = LocalGitService()
    project = ProjectService(factory, git).initialize(git_repo)
    draft = GoalDraft(
        goal="Events",
        scope=("main.py",),
        definition_of_done=("events persisted",),
        criteria=(
            CriterionDefinition(
                key="AC-1", description="exists", validation_spec=FileValidation(path="main.py")
            ),
        ),
    )
    run, _ = GoalService(factory).create(
        project, "events", "feature/events", git.status(git_repo).head, draft
    )

    def append(number: int) -> int:
        with factory() as uow:
            event = uow.events.append(
                run.id,
                EventDraft(
                    event_type=EventType.PLAN_REVISED,
                    occurred_at=run.created_at,
                    idempotency_key=f"fixture:{number}",
                    payload=EventPayload(plan_version=number),
                ),
            )
            uow.commit()
            return event.sequence

    with ThreadPoolExecutor(max_workers=4) as pool:
        sequences = list(pool.map(append, range(8)))
    assert len(set(sequences)) == 8
    assert append(0) == sequences[0]
    with factory() as uow:
        events = uow.events.list(run.id)
        assert [event.sequence for event in events] == list(range(1, len(events) + 1))
        before = len(events)
        with pytest.raises(ConflictError):
            uow.events.append(
                run.id,
                EventDraft(
                    event_type=EventType.PLAN_REVISED,
                    occurred_at=run.created_at,
                    idempotency_key="fixture:0",
                    payload=EventPayload(plan_version=99),
                ),
            )
        uow.rollback()
        assert len(uow.events.list(run.id)) == before
    with Session(database) as session, pytest.raises(DBAPIError):
        session.execute(update(EventRow).where(EventRow.run_id == run.id).values(status="tampered"))
