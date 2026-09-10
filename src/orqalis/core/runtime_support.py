from datetime import datetime
from uuid import UUID, uuid5

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.domain.agent import ActorSession, ActorStatus, ActorType
from orqalis.domain.errors import InputError, NotFoundError
from orqalis.domain.events import Event, EventDraft, EventPayload, EventType
from orqalis.domain.run import Run
from orqalis.observability.timing import EventTimingProjection


def require_key(key: str) -> None:
    if not key.strip() or len(key) > 120:
        raise InputError("Command idempotency key must contain 1..120 characters")


def locked_run(uow: ProjectUnitOfWork, run_id: UUID) -> Run:
    run = uow.runs.get(run_id, for_update=True)
    if run is None:
        raise NotFoundError("Run not found")
    return run


def emit(
    uow: ProjectUnitOfWork,
    run: Run,
    kind: EventType,
    key: str,
    at: datetime,
    payload: EventPayload,
    actor_id: UUID | None = None,
    task_id: UUID | None = None,
    execution_id: UUID | None = None,
) -> Event:
    return uow.events.append(
        run.id,
        EventDraft(
            event_type=kind,
            occurred_at=at,
            idempotency_key=key,
            payload=payload,
            phase=run.ui_phase,
            actor_session_id=actor_id,
            task_id=task_id,
            task_execution_id=execution_id,
        ),
    )


def orchestrator_actor(uow: ProjectUnitOfWork, run: Run, at: datetime) -> ActorSession:
    actor_id = uuid5(run.id, "orchestrator")
    actor = next((actor for actor in uow.runtime.actors(run.id) if actor.id == actor_id), None)
    if actor:
        return actor
    actor = ActorSession(
        id=actor_id,
        run_id=run.id,
        actor_type=ActorType.ORCHESTRATOR,
        status=ActorStatus.IDLE,
        started_at=at,
        created_at=at,
    )
    uow.runtime.save_actor(actor)
    emit(
        uow,
        run,
        EventType.ACTOR_STARTED,
        "orchestrator:created",
        at,
        EventPayload(status=actor.status),
        actor_id=actor.id,
    )
    return actor


def set_actor_status(
    uow: ProjectUnitOfWork,
    run: Run,
    actor: ActorSession,
    status: ActorStatus,
    key: str,
    at: datetime,
) -> ActorSession:
    terminal = status in {ActorStatus.COMPLETE, ActorStatus.CANCELLED, ActorStatus.FAILED}
    event = emit(
        uow,
        run,
        EventType.ACTOR_COMPLETED if terminal else EventType.ACTOR_STATUS_CHANGED,
        key,
        at,
        EventPayload(previous_status=actor.status, status=status),
        actor_id=actor.id,
    )
    timing = EventTimingProjection().actor(uow.events.list(run.id), actor.id, event.occurred_at)
    updated = actor.model_copy(
        update={
            "status": status,
            "completed_at": event.occurred_at if terminal else None,
            "working_ms": timing.active_ms,
            "waiting_ms": timing.waiting_ms,
            "blocked_ms": timing.blocked_ms,
        }
    )
    uow.runtime.save_actor(updated)
    return updated
