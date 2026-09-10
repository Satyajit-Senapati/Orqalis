from datetime import datetime

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.run import Run
from orqalis.domain.task import TaskStatus
from orqalis.domain.timing import PhaseExecution
from orqalis.observability.timing import EventTimingProjection


def update_phase(
    uow: ProjectUnitOfWork,
    run: Run,
    key: str,
    at: datetime,
    status: TaskStatus = TaskStatus.RUNNING,
    terminal: bool = False,
) -> None:
    phases = uow.runtime.phases(run.id)
    current = next((phase for phase in reversed(phases) if phase.completed_at is None), None)
    if current and (current.phase != run.ui_phase or terminal):
        ended_status = status if terminal else TaskStatus.SUCCEEDED
        event = emit(
            uow,
            run.model_copy(update={"ui_phase": current.phase}),
            EventType.PHASE_COMPLETED,
            f"{key}:phase-end",
            at,
            EventPayload(status=ended_status, phase_execution_id=current.id),
        )
        timing = EventTimingProjection().phase(
            uow.events.list(run.id), current.id, event.occurred_at
        )
        uow.runtime.save_phase(
            current.model_copy(
                update={
                    "status": ended_status,
                    "completed_at": event.occurred_at,
                    "active_ms": timing.active_ms,
                    "waiting_ms": timing.waiting_ms,
                    "blocked_ms": timing.blocked_ms,
                }
            )
        )
        current = None
    if terminal:
        return
    if current is None:
        current = PhaseExecution(
            run_id=run.id,
            phase=run.ui_phase,
            started_at=at,
            created_at=at,
            iteration=1 + sum(phase.phase == run.ui_phase for phase in phases),
            status=status,
        )
        uow.runtime.save_phase(current)
        emit(
            uow,
            run,
            EventType.PHASE_STARTED,
            f"{key}:phase-start",
            at,
            EventPayload(status=status, phase_execution_id=current.id),
        )
    elif current.status != status:
        uow.runtime.save_phase(current.model_copy(update={"status": status}))
        emit(
            uow,
            run,
            EventType.PHASE_STATUS_CHANGED,
            f"{key}:phase-status",
            at,
            EventPayload(
                previous_status=current.status, status=status, phase_execution_id=current.id
            ),
        )
