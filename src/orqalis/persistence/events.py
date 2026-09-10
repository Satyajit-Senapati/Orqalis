from uuid import UUID

from opentelemetry import trace
from sqlalchemy import select
from sqlalchemy.orm import Session

from orqalis.domain.errors import ConflictError, NotFoundError
from orqalis.domain.events import Event, EventDraft
from orqalis.persistence.runtime_models import EventRow
from orqalis.persistence.workflow_models import RunRow
from orqalis.security.redaction import safe_diagnostic


class SQLEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def append(self, run_id: UUID, draft: EventDraft) -> Event:
        run = self.session.scalar(select(RunRow).where(RunRow.id == run_id).with_for_update())
        if run is None:
            raise NotFoundError("Run not found")
        existing = self.by_key(run_id, draft.idempotency_key)
        if existing:
            if (
                existing.event_type != draft.event_type
                or existing.payload != draft.payload
                or existing.task_id != draft.task_id
                or existing.actor_session_id != draft.actor_session_id
                or existing.task_execution_id != draft.task_execution_id
                or existing.phase != draft.phase
            ):
                raise ConflictError("Idempotency key reused for a different event")
            return existing
        payload = draft.payload.model_dump_json()
        if safe_diagnostic(payload) != payload:
            raise ConflictError("Unsafe event payload rejected")
        last = self.session.scalar(
            select(EventRow.occurred_at)
            .where(EventRow.run_id == run_id)
            .order_by(EventRow.sequence.desc())
            .limit(1)
        )
        # Keep intervals ordered if the wall clock moves backwards between commands.
        timestamp = max(last, draft.occurred_at) if last else draft.occurred_at
        span = trace.get_current_span().get_span_context()
        event = Event(
            project_id=run.project_id,
            run_id=run_id,
            sequence=run.last_event_sequence + 1,
            **draft.model_dump(exclude={"occurred_at"}),
            occurred_at=timestamp,
            status=draft.payload.status,
            trace_id=format(span.trace_id, "032x") if span.is_valid else None,
        )
        self.session.add(
            EventRow(
                **event.model_dump(exclude={"payload"}),
                payload=event.payload.model_dump(mode="json"),
            )
        )
        run.last_event_sequence = event.sequence
        self.session.flush()
        return event

    def list(self, run_id: UUID, after: int = 0, limit: int | None = None) -> tuple[Event, ...]:
        return tuple(
            Event.model_validate(row, from_attributes=True)
            for row in self.session.scalars(
                select(EventRow)
                .where(EventRow.run_id == run_id, EventRow.sequence > after)
                .order_by(EventRow.sequence)
                .limit(limit)
            )
        )

    def by_key(self, run_id: UUID, key: str) -> Event | None:
        row = self.session.scalar(
            select(EventRow).where(EventRow.run_id == run_id, EventRow.idempotency_key == key)
        )
        return Event.model_validate(row, from_attributes=True) if row else None
