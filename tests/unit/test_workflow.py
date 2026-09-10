from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from orqalis.core.scheduler import dispatch_wave, plan_completion, ready_tasks
from orqalis.core.state_machine import validate_transition
from orqalis.domain.agent import AgentRole
from orqalis.domain.errors import ConflictError
from orqalis.domain.events import Event, EventPayload, EventType
from orqalis.domain.plan import TaskPlan
from orqalis.domain.run import RunState
from orqalis.domain.task import Task, TaskDependency, TaskStatus
from orqalis.observability.timing import EventTimingProjection


def task(run_id: object, role: AgentRole = AgentRole.DEVELOPER) -> Task:
    return Task.model_validate(
        dict(
            run_id=run_id,
            description="task",
            expected_outcome="done",
            validation_method="test",
            preferred_role=role,
        )
    )


def test_dag_validation_readiness_parallel_readers_and_serial_writers() -> None:
    run_id = uuid4()
    first, second = task(run_id), task(run_id)
    reader = task(run_id, AgentRole.REVIEWER)
    plan = TaskPlan(
        run_id=run_id, goal_version_id=uuid4(), version=1, tasks=(first, second, reader)
    )
    assert len(ready_tasks(plan)) == 3
    assert dispatch_wave(plan, 3) == (first, reader)
    dependent = plan.model_copy(
        update={"dependencies": (TaskDependency(task_id=second.id, depends_on_task_id=first.id),)}
    )
    assert ready_tasks(dependent) == (first, reader)
    with pytest.raises(ValidationError, match="cycle"):
        TaskPlan.model_validate(
            {
                **plan.model_dump(),
                "dependencies": (
                    TaskDependency(task_id=second.id, depends_on_task_id=first.id),
                    TaskDependency(task_id=first.id, depends_on_task_id=second.id),
                ),
            }
        )
    with pytest.raises(ValidationError, match="unknown"):
        TaskPlan.model_validate(
            {
                **plan.model_dump(),
                "dependencies": (TaskDependency(task_id=second.id, depends_on_task_id=uuid4()),),
            }
        )
    assert plan_completion(plan) == 0
    complete = plan.model_copy(
        update={
            "tasks": (
                first.model_copy(update={"status": TaskStatus.SUCCEEDED}),
                second,
                reader,
            )
        }
    )
    assert plan_completion(complete) == pytest.approx(100 / 3)


def test_invalid_transitions_and_resume() -> None:
    validate_transition(RunState.RECEIVED, RunState.CONTEXT_SYNC)
    with pytest.raises(ConflictError):
        validate_transition(RunState.RECEIVED, RunState.COMPLETED)
    with pytest.raises(ConflictError):
        validate_transition(RunState.COMPLETED, RunState.EXECUTING)
    with pytest.raises(ConflictError):
        validate_transition(RunState.PAUSED, RunState.TESTING, RunState.EXECUTING)
    validate_transition(RunState.PAUSED, RunState.EXECUTING, RunState.EXECUTING)


def test_timing_uses_intervals_not_nested_tool_durations() -> None:
    at = datetime(2026, 1, 1, tzinfo=UTC)
    run_id, project_id, actor_id = uuid4(), uuid4(), uuid4()
    events = tuple(
        Event(
            project_id=project_id,
            run_id=run_id,
            sequence=index + 1,
            event_type=kind,
            occurred_at=at + timedelta(seconds=seconds),
            actor_session_id=actor_id,
            payload=EventPayload(status=status),
            idempotency_key=str(index),
        )
        for index, (kind, seconds, status) in enumerate(
            [
                (EventType.ACTOR_STARTED, 0, "WORKING"),
                (EventType.TOOL_STARTED, 1, "RUNNING"),
                (EventType.ACTOR_STATUS_CHANGED, 4, "WAITING_FOR_DEPENDENCY"),
                (EventType.TOOL_COMPLETED, 6, "SUCCEEDED"),
                (EventType.ACTOR_STATUS_CHANGED, 7, "BLOCKED"),
                (EventType.ACTOR_COMPLETED, 9, "COMPLETE"),
            ]
        )
    )
    timing = EventTimingProjection().actor(events, actor_id, at + timedelta(seconds=50))
    assert (timing.wall_ms, timing.active_ms, timing.waiting_ms, timing.blocked_ms) == (
        9000,
        4000,
        3000,
        2000,
    )
