from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from orqalis.core.approvals import task_approval_reason
from orqalis.domain.agent import AgentRole
from orqalis.domain.events import Event, EventPayload, EventType
from orqalis.domain.execution import ApprovedCommand, ExecutionPolicy
from orqalis.domain.task import Task
from orqalis.observability.timing import EventTimingProjection


def _event(
    run_id: UUID,
    project_id: UUID,
    sequence: int,
    seconds: int,
    kind: EventType,
    status: str,
    *,
    request_id: UUID | None = None,
    actor_id: UUID | None = None,
    operator: bool = False,
) -> Event:
    return Event(
        project_id=project_id,
        run_id=run_id,
        sequence=sequence,
        occurred_at=datetime(2026, 9, 14, tzinfo=UTC) + timedelta(seconds=seconds),
        event_type=kind,
        idempotency_key=(
            f"operator-approval:{request_id}:{sequence}" if operator else f"other:{sequence}"
        ),
        actor_session_id=actor_id,
        payload=EventPayload(
            status=status,
            approval_request_id=request_id,
            approval_stage="GOAL" if request_id else None,
        ),
    )


def test_run_approval_wait_and_rejection_are_reconstructed_from_operator_events() -> None:
    run_id, project_id, actor_id = uuid4(), uuid4(), uuid4()
    first, second = uuid4(), uuid4()
    records = (
        (0, EventType.RUN_STARTED, "GOAL_DEFINED", None, False),
        (5, EventType.APPROVAL_REQUESTED, "PENDING", first, True),
        (10, EventType.APPROVAL_RECORDED, "APPROVED", first, True),
        (20, EventType.RUN_STATE_CHANGED, "PLANNED", None, False),
        (23, EventType.APPROVAL_REQUESTED, "PENDING", second, True),
        (25, EventType.APPROVAL_RECORDED, "REJECTED", second, True),
        (30, EventType.RUN_STATE_CHANGED, "EXECUTING", None, False),
        # A delivery-policy attestation is not an operator decision.
        (35, EventType.APPROVAL_RECORDED, "PENDING", second, False),
        (40, EventType.RUN_COMPLETED, "COMPLETED", None, False),
    )
    events = tuple(
        _event(
            run_id,
            project_id,
            i,
            second_at,
            kind,
            status,
            request_id=request,
            actor_id=actor_id,
            operator=operator,
        )
        for i, (second_at, kind, status, request, operator) in enumerate(records, 1)
    )
    timing = EventTimingProjection().run(
        events, datetime(2026, 9, 14, tzinfo=UTC) + timedelta(seconds=60)
    )
    assert (timing.wall_ms, timing.active_ms, timing.waiting_ms, timing.blocked_ms) == (
        40000,
        18000,
        17000,
        5000,
    )


def test_actor_timing_counts_persisted_approval_status_transitions() -> None:
    run_id, project_id, actor_id = uuid4(), uuid4(), uuid4()
    records = (
        (0, EventType.ACTOR_STARTED, "WORKING"),
        (5, EventType.ACTOR_STATUS_CHANGED, "WAITING_FOR_DEPENDENCY"),
        (25, EventType.ACTOR_STATUS_CHANGED, "BLOCKED"),
        (30, EventType.ACTOR_STATUS_CHANGED, "WORKING"),
        (40, EventType.ACTOR_COMPLETED, "COMPLETE"),
    )
    events = tuple(
        _event(run_id, project_id, i, seconds, kind, status, actor_id=actor_id)
        for i, (seconds, kind, status) in enumerate(records, 1)
    )
    timing = EventTimingProjection().actor(
        events, actor_id, datetime(2026, 9, 14, tzinfo=UTC) + timedelta(seconds=60)
    )
    assert (timing.wall_ms, timing.active_ms, timing.waiting_ms, timing.blocked_ms) == (
        40000,
        15000,
        20000,
        5000,
    )


def test_task_start_resumes_run_time_after_task_approval() -> None:
    run_id, project_id, request_id = uuid4(), uuid4(), uuid4()
    records = (
        (0, EventType.RUN_STARTED, "EXECUTING", None, False),
        (5, EventType.APPROVAL_REQUESTED, "PENDING", request_id, True),
        (10, EventType.APPROVAL_RECORDED, "APPROVED", request_id, True),
        (12, EventType.TASK_STARTED, "RUNNING", None, False),
        (20, EventType.RUN_COMPLETED, "COMPLETED", None, False),
    )
    events = tuple(
        _event(run_id, project_id, i, seconds, kind, status, request_id=request, operator=operator)
        for i, (seconds, kind, status, request, operator) in enumerate(records, 1)
    )
    timing = EventTimingProjection().run(
        events, datetime(2026, 9, 14, tzinfo=UTC) + timedelta(seconds=60)
    )
    assert (timing.wall_ms, timing.active_ms, timing.waiting_ms) == (
        20000,
        13000,
        7000,
    )


def test_task_approval_reason_exposes_scope_without_leaking_credentials() -> None:
    task = Task(
        run_id=uuid4(),
        description="Update API_KEY=supersecret in the widget service",
        expected_outcome="Widget works",
        validation_method="pytest",
        preferred_role=AgentRole.DEVELOPER,
    )
    policy = ExecutionPolicy(
        write_paths=("src/**", "tests/**"),
        commands=(ApprovedCommand(id="pytest", argv=("pytest",)),),
        command_mode="trusted_local",
    )
    reason = task_approval_reason(task, policy)
    assert str(task.id) in reason
    assert "developer" in reason
    assert "src/**" in reason and "tests/**" in reason
    assert "pytest" in reason
    assert "supersecret" not in reason
    assert len(reason) <= 1000
