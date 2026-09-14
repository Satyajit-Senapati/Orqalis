from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid5

from orqalis.core.approval_guard import require_approval
from orqalis.core.approval_subjects import requirements_task_subject, task_subject
from orqalis.core.approvals import task_approval_reason
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import (
    emit,
    locked_run,
    orchestrator_actor,
    require_key,
    set_actor_status,
)
from orqalis.core.scheduler import WRITE_ROLES, ready_tasks
from orqalis.domain.agent import ActorSession, ActorStatus, ActorType, AgentRole
from orqalis.domain.approval import ApprovalStage
from orqalis.domain.base import utc_now
from orqalis.domain.errors import ConflictError, NotFoundError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.run import Run, RunState
from orqalis.domain.task import TaskExecution, TaskStatus
from orqalis.observability.timing import EventTimingProjection

_TRANSITIONS = {
    TaskStatus.RUNNING: {
        TaskStatus.WAITING,
        TaskStatus.BLOCKED,
        TaskStatus.SUCCEEDED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.WAITING: {
        TaskStatus.RUNNING,
        TaskStatus.BLOCKED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.BLOCKED: {TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED},
}
_TASK_EVENTS = {
    TaskStatus.RUNNING: EventType.TASK_STARTED,
    TaskStatus.WAITING: EventType.TASK_WAITING,
    TaskStatus.BLOCKED: EventType.TASK_BLOCKED,
    TaskStatus.SUCCEEDED: EventType.TASK_COMPLETED,
    TaskStatus.FAILED: EventType.TASK_FAILED,
    TaskStatus.CANCELLED: EventType.TASK_CANCELLED,
}
_ACTOR_STATUSES = {
    TaskStatus.RUNNING: ActorStatus.WORKING,
    TaskStatus.WAITING: ActorStatus.WAITING_FOR_DEPENDENCY,
    TaskStatus.BLOCKED: ActorStatus.BLOCKED,
    TaskStatus.SUCCEEDED: ActorStatus.COMPLETE,
    TaskStatus.FAILED: ActorStatus.FAILED,
    TaskStatus.CANCELLED: ActorStatus.CANCELLED,
}
_EXECUTION_STATES = {
    RunState.ANALYZING,
    RunState.MEMORY_FINALIZATION,
    RunState.DELIVERY_VALIDATION,
    RunState.COMMITTING,
    RunState.PUSHING,
    RunState.EXECUTING,
    RunState.TESTING,
    RunState.REVIEWING,
    RunState.DOCUMENTING,
    RunState.CHANGE_GUARD,
}


def refresh_ready(uow: ProjectUnitOfWork, run: Run, key: str, at: datetime) -> None:
    plan = uow.runtime.get_plan(run.id, run.plan_version)
    if plan:
        for task in ready_tasks(plan):
            if task.status == TaskStatus.PENDING:
                uow.runtime.save_task(
                    task.model_copy(update={"status": TaskStatus.READY, "ready_at": at})
                )
                emit(
                    uow,
                    run,
                    EventType.TASK_READY,
                    f"{key}:ready:{task.id}",
                    at,
                    EventPayload(status=TaskStatus.READY),
                    task_id=task.id,
                )


class TaskRuntime:
    """Internal deterministic task state operations used by Orchestrator."""

    def __init__(
        self, unit_of_work: Callable[[], ProjectUnitOfWork], clock: Callable[[], datetime] = utc_now
    ) -> None:
        self.unit_of_work, self.clock = unit_of_work, clock

    def start(self, run_id: UUID, task_id: UUID, key: str) -> TaskExecution:
        require_key(key)
        with self.unit_of_work() as uow:
            run = locked_run(uow, run_id)
            existing = uow.events.by_key(run_id, f"{key}:task")
            if existing:
                if existing.task_id != task_id or existing.event_type != EventType.TASK_STARTED:
                    raise ConflictError("Idempotency key belongs to another task command")
                return next(
                    item
                    for item in uow.runtime.executions(run_id)
                    if item.id == existing.task_execution_id
                )
            if run.state not in _EXECUTION_STATES:
                raise ConflictError("Run is not executing work")
            plan = uow.runtime.get_plan(run_id, run.plan_version)
            if run.state == RunState.ANALYZING:
                task = next(
                    (
                        t
                        for t in uow.runtime.tasks(run_id)
                        if t.id == task_id
                        and t.preferred_role == AgentRole.REQUIREMENTS
                        and t.plan_version == 0
                        and t.status in {TaskStatus.READY, TaskStatus.PENDING}
                    ),
                    None,
                )
                if run.current_goal_version_id:
                    raise ConflictError("Requirements have already been defined")
            else:
                if not plan or plan.goal_version_id != run.current_goal_version_id:
                    raise ConflictError("Current goal requires a valid plan")
                task = next((item for item in ready_tasks(plan) if item.id == task_id), None)
            if task is None:
                raise ConflictError("Task is not dependency-ready")
            control = uow.approvals.policy(run_id)
            if control is not None and control.requires(ApprovalStage.TASK):
                if run.state == RunState.ANALYZING:
                    digest = requirements_task_subject(task)
                    execution_policy = None
                else:
                    workspace = uow.execution.workspace(run_id)
                    if workspace is None:
                        raise PolicyDeniedError(
                            "Task approval requires a persisted workspace policy"
                        )
                    execution_policy = workspace.policy
                    digest = task_subject(task, execution_policy)
                require_approval(
                    uow,
                    run,
                    ApprovalStage.TASK,
                    run.plan_version,
                    digest,
                    task_approval_reason(task, execution_policy),
                )
            if task.preferred_role in WRITE_ROLES and any(
                item.preferred_role in WRITE_ROLES
                and item.status in {TaskStatus.RUNNING, TaskStatus.WAITING, TaskStatus.BLOCKED}
                for item in (plan.tasks if plan else ())
            ):
                raise ConflictError("Another writer owns the workspace")
            at = self.clock()
            actor = ActorSession(
                id=uuid5(run_id, f"{key}:actor"),
                run_id=run_id,
                actor_type=ActorType.AGENT,
                role=task.preferred_role,
                status=ActorStatus.WORKING,
                current_task_id=task_id,
                started_at=at,
                created_at=at,
                tasks_attempted=1,
            )
            uow.runtime.save_actor(actor)
            execution = TaskExecution(
                id=uuid5(run_id, f"{key}:attempt"),
                run_id=run_id,
                task_id=task_id,
                attempt=task.attempt_count + 1,
                assigned_actor_session_id=actor.id,
                created_at=at,
                ready_at=task.ready_at or at,
                started_at=at,
                status=TaskStatus.RUNNING,
                queue_ms=max(0, int((at - (task.ready_at or at)).total_seconds() * 1000)),
            )
            uow.runtime.save_execution(execution)
            uow.runtime.save_task(
                task.model_copy(
                    update={
                        "status": TaskStatus.RUNNING,
                        "started_at": at,
                        "attempt_count": execution.attempt,
                    }
                )
            )
            emit(
                uow,
                run,
                EventType.ACTOR_STARTED,
                f"{key}:actor",
                at,
                EventPayload(status=ActorStatus.WORKING),
                actor.id,
                task_id,
                execution.id,
            )
            emit(
                uow,
                run,
                EventType.TASK_STARTED,
                f"{key}:task",
                at,
                EventPayload(status=TaskStatus.RUNNING),
                actor.id,
                task_id,
                execution.id,
            )
            coordinator = orchestrator_actor(uow, run, at)
            set_actor_status(
                uow, run, coordinator, ActorStatus.WAITING_FOR_DEPENDENCY, f"{key}:coordinator", at
            )
            uow.commit()
            return execution

    def transition(
        self, run_id: UUID, execution_id: UUID, status: TaskStatus, key: str
    ) -> TaskExecution:
        require_key(key)
        with self.unit_of_work() as uow:
            run = locked_run(uow, run_id)
            if run.state not in _EXECUTION_STATES and status != TaskStatus.CANCELLED:
                raise ConflictError("Run is not executing work")
            result = self.transition_in_transaction(
                uow, run, execution_id, status, key, self.clock()
            )
            uow.commit()
            return result

    def transition_in_transaction(
        self,
        uow: ProjectUnitOfWork,
        run: Run,
        execution_id: UUID,
        status: TaskStatus,
        key: str,
        at: datetime,
    ) -> TaskExecution:
        execution = next(
            (item for item in uow.runtime.executions(run.id) if item.id == execution_id), None
        )
        if execution is None:
            raise NotFoundError("Task execution not found")
        existing = uow.events.by_key(run.id, f"{key}:task")
        if existing:
            if existing.task_execution_id != execution_id or existing.payload.status != status:
                raise ConflictError("Idempotency key belongs to another task command")
            return execution
        if status not in _TRANSITIONS.get(execution.status, set()):
            raise ConflictError("Invalid task-attempt transition")
        task = next(item for item in uow.runtime.tasks(run.id) if item.id == execution.task_id)
        actor = next(
            item
            for item in uow.runtime.actors(run.id)
            if item.id == execution.assigned_actor_session_id
        )
        event = emit(
            uow,
            run,
            _TASK_EVENTS[status],
            f"{key}:task",
            at,
            EventPayload(previous_status=execution.status, status=status),
            actor.id,
            task.id,
            execution.id,
        )
        timing = EventTimingProjection().task(
            uow.events.list(run.id), execution.id, event.occurred_at
        )
        terminal = status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}
        updated = execution.model_copy(
            update={
                "status": status,
                "completed_at": event.occurred_at if terminal else None,
                "active_ms": timing.active_ms,
                "waiting_ms": timing.waiting_ms,
                "blocked_ms": timing.blocked_ms,
            }
        )
        uow.runtime.save_execution(updated)
        uow.runtime.save_task(
            task.model_copy(
                update={
                    "status": status,
                    "completed_at": event.occurred_at if terminal else None,
                }
            )
        )
        actor = actor.model_copy(
            update={
                "tasks_completed": 1 if status == TaskStatus.SUCCEEDED else 0,
                "tasks_failed": 1 if status == TaskStatus.FAILED else 0,
                "current_task_id": None if terminal else task.id,
            }
        )
        set_actor_status(
            uow, run, actor, _ACTOR_STATUSES[status], f"{key}:actor", event.occurred_at
        )
        if terminal:
            remaining = [
                item
                for item in uow.runtime.executions(run.id)
                if item.status in {TaskStatus.RUNNING, TaskStatus.WAITING, TaskStatus.BLOCKED}
            ]
            coordinator = orchestrator_actor(uow, run, event.occurred_at)
            set_actor_status(
                uow,
                run,
                coordinator,
                ActorStatus.WAITING_FOR_DEPENDENCY if remaining else ActorStatus.WORKING,
                f"{key}:coordinator",
                event.occurred_at,
            )
        if status == TaskStatus.SUCCEEDED:
            refresh_ready(uow, run, key, event.occurred_at)
        return updated
