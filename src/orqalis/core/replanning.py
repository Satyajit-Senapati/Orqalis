from collections.abc import Callable

from orqalis.core.approval_guard import require_approval
from orqalis.core.approval_subjects import goal_subject
from orqalis.core.planning import plan_identity
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit, locked_run, require_key
from orqalis.core.task_runtime import TaskRuntime, refresh_ready
from orqalis.domain.approval import ApprovalStage
from orqalis.domain.base import utc_now
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.plan import TaskPlan
from orqalis.domain.run import Run, RunState
from orqalis.domain.task import TaskStatus
from orqalis.security.redaction import safe_diagnostic


class GoalReplanning:
    """Orchestrator-owned plan replacement after an explicit goal revision."""

    def __init__(self, factory: Callable[[], ProjectUnitOfWork]) -> None:
        self.factory = factory

    def install(self, plan: TaskPlan, key: str) -> Run:
        require_key(key)
        with self.factory() as lease:
            if not lease.execution.try_run_lock(plan.run_id):
                raise ConflictError("A worker owns this run")
            with self.factory() as uow:
                run = locked_run(uow, plan.run_id)
                if uow.events.by_key(run.id, f"replan:{key}"):
                    stored = uow.runtime.get_plan(run.id, plan.version)
                    if not stored or plan_identity(stored) != plan_identity(plan):
                        raise ConflictError("Replan key belongs to another plan")
                    return run
                current = uow.runtime.get_plan(run.id, run.plan_version)
                if (
                    run.state not in {RunState.PAUSED, RunState.HUMAN_REVIEW_REQUIRED}
                    or not current
                ):
                    raise ConflictError("Replanning requires a suspended run with an existing plan")
                if current.goal_version_id == run.current_goal_version_id:
                    raise ConflictError("Replanning requires an explicitly revised goal")
                if uow.events.by_key(run.id, "delivery:policy"):
                    raise PolicyDeniedError(
                        "Delivery has started; use a new run for a changed goal"
                    )
                if (
                    plan.goal_version_id != run.current_goal_version_id
                    or plan.version != run.plan_version + 1
                ):
                    raise ConflictError("New plan must use the current goal and next plan version")
                history = {t.id for t in uow.runtime.tasks(run.id)}
                if any(
                    t.id in history
                    or t.status != TaskStatus.PENDING
                    or t.attempt_count
                    or t.plan_version != plan.version
                    for t in plan.tasks
                ):
                    raise ConflictError(
                        "Replacement work must have fresh, unexecuted task identities"
                    )
                goal = uow.runs.get_goal(plan.goal_version_id)
                if goal is None:
                    raise ConflictError("Current goal missing")
                require_approval(
                    uow,
                    run,
                    ApprovalStage.GOAL,
                    goal.goal.version,
                    goal_subject(goal),
                    "Approve revised goal before replanning",
                )
                affected = {c for t in plan.tasks for c in t.acceptance_criterion_ids}
                ids = {c.id for c in goal.criteria}
                if (
                    not affected <= ids
                    or not {c.id for c in goal.criteria if c.priority == "required"} <= affected
                ):
                    raise ConflictError(
                        "Replacement plan must cover only current required acceptance"
                    )
                if safe_diagnostic(plan.model_dump_json()) != plan.model_dump_json():
                    raise PolicyDeniedError("Unsafe plan")
                at = utc_now()
                for attempt in uow.runtime.executions(run.id):
                    if attempt.status == TaskStatus.RUNNING:
                        raise ConflictError("Active work must reach a checkpoint before replanning")
                    if attempt.status in {TaskStatus.WAITING, TaskStatus.BLOCKED}:
                        TaskRuntime(self.factory).transition_in_transaction(
                            uow,
                            run,
                            attempt.id,
                            TaskStatus.CANCELLED,
                            f"replan:{key}:{attempt.id}",
                            at,
                        )
                for task in current.tasks:
                    if task.status in {TaskStatus.PENDING, TaskStatus.READY}:
                        uow.runtime.save_task(
                            task.model_copy(
                                update={"status": TaskStatus.CANCELLED, "completed_at": at}
                            )
                        )
                        emit(
                            uow,
                            run,
                            EventType.TASK_CANCELLED,
                            f"replan:{key}:cancel:{task.id}",
                            at,
                            EventPayload(status="CANCELLED", reason="Explicit goal revision"),
                            task_id=task.id,
                        )
                uow.runtime.save_plan(plan)
                updated = run.model_copy(
                    update={"plan_version": plan.version, "resume_state": RunState.PLANNED}
                )
                uow.runs.save(updated)
                emit(
                    uow,
                    updated,
                    EventType.PLAN_REVISED,
                    f"replan:{key}",
                    at,
                    EventPayload(
                        plan_version=plan.version,
                        goal_version_id=plan.goal_version_id,
                        task_ids=tuple(t.id for t in plan.tasks),
                        reason="Explicit goal revision",
                    ),
                )
                for task in plan.tasks:
                    emit(
                        uow,
                        updated,
                        EventType.TASK_CREATED,
                        f"replan:{key}:task:{task.id}",
                        at,
                        EventPayload(status=task.status),
                        task_id=task.id,
                    )
                refresh_ready(uow, updated, f"replan:{key}", at)
                uow.commit()
                return locked_run(uow, run.id)
