from datetime import UTC, datetime, timedelta
from uuid import uuid4

from orqalis.domain.events import Event, EventPayload, EventType
from orqalis.domain.plan import TaskPlan
from orqalis.domain.task import Task, TaskDependency
from orqalis.domain.timing import TimingBreakdown
from orqalis.observability.analytics import statistics, timeline
from orqalis.observability.timing import EventTimingProjection


def test_parallel_and_waiting_intervals_are_reconstructed_without_double_counting() -> None:
    run, project, first, second = uuid4(), uuid4(), uuid4(), uuid4()
    start = datetime(2026, 9, 10, tzinfo=UTC)
    tasks = tuple(
        Task(run_id=run, description=name, expected_outcome=name, validation_method="test")
        for name in ("first", "second", "join")
    )
    records = (
        (0, first, tasks[0].id, EventType.TASK_STARTED, "RUNNING"),
        (0, second, tasks[1].id, EventType.TASK_STARTED, "RUNNING"),
        (3, first, tasks[0].id, EventType.TASK_WAITING, "WAITING"),
        (5, second, tasks[1].id, EventType.TASK_COMPLETED, "SUCCEEDED"),
        (7, first, tasks[0].id, EventType.TASK_STARTED, "RUNNING"),
        (10, first, tasks[0].id, EventType.TASK_COMPLETED, "SUCCEEDED"),
    )
    events = tuple(
        Event(
            project_id=project,
            run_id=run,
            sequence=i + 1,
            occurred_at=start + timedelta(seconds=t),
            event_type=kind,
            task_execution_id=attempt,
            task_id=task,
            idempotency_key=str(i),
            payload=EventPayload(status=status),
        )
        for i, (t, attempt, task, kind, status) in enumerate(records)
    )
    segments = timeline(events, start + timedelta(hours=1))
    timer = EventTimingProjection()
    timing = {
        tasks[0].id: timer.task(events, first, start + timedelta(hours=1)),
        tasks[1].id: timer.task(events, second, start + timedelta(hours=1)),
    }
    assert timing[tasks[0].id].active_ms == 6000
    assert timing[tasks[0].id].waiting_ms == 4000
    assert max(s.ended_at for s in segments) == start + timedelta(seconds=10)
    plan = TaskPlan(
        run_id=run,
        goal_version_id=uuid4(),
        version=1,
        tasks=tasks,
        dependencies=tuple(
            TaskDependency(task_id=tasks[2].id, depends_on_task_id=t.id) for t in tasks[:2]
        ),
    )
    stats = statistics(segments, plan, timing, TimingBreakdown(wall_ms=10000), (), 0, ())
    assert stats.max_parallel_tasks == 2
    assert stats.mean_parallel_tasks == 1.1
    assert stats.critical_path_working_ms == 6000
    assert stats.critical_path_task_ids == (tasks[0].id, tasks[2].id)
    assert stats.reported_input_tokens is None and stats.first_pass_success is None
