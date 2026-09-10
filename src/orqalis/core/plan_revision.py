from collections.abc import Callable
from datetime import datetime

from orqalis.core.planning import plan_identity
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit, locked_run, require_key
from orqalis.core.task_runtime import refresh_ready
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.plan import TaskPlan
from orqalis.domain.run import Run, RunState
from orqalis.domain.task import TaskStatus
from orqalis.security.redaction import safe_diagnostic


class PlanRevisionService:
    """Internal additive plan revision, invoked only through Orchestrator."""

    def __init__(
        self, factory: Callable[[], ProjectUnitOfWork], clock: Callable[[], datetime]
    ) -> None:
        self.factory, self.clock = factory, clock

    def install_repair(self, plan: TaskPlan, key: str) -> Run:
        return self._install(plan, key, repair=True)

    def install_delivery(self, plan: TaskPlan, key: str) -> Run:
        return self._install(plan, key, repair=False)

    def _install(self, plan: TaskPlan, key: str, *, repair: bool) -> Run:
        require_key(key)
        with self.factory() as uow:
            run = locked_run(uow, plan.run_id)
            replay = uow.events.by_key(run.id, f"{key}:revised")
            if replay:
                stored = uow.runtime.get_plan(run.id, plan.version)
                if not stored or plan_identity(stored) != plan_identity(plan):
                    raise ConflictError("Repair key references another plan")
                return run
            if (
                repair
                and (
                    run.state != RunState.REPAIR_PLANNING
                    or run.repair_iteration >= run.max_repair_iterations
                )
            ) or (not repair and run.state != RunState.REVIEWING):
                raise PolicyDeniedError("Repair is unavailable or its configured limit was reached")
            if (
                plan.version != run.plan_version + 1
                or plan.goal_version_id != run.current_goal_version_id
            ):
                raise ConflictError(
                    "Repair must preserve the current goal and increment plan version"
                )
            current = uow.runtime.get_plan(run.id, run.plan_version)
            goal = uow.runs.get_goal(plan.goal_version_id)
            if current is None or goal is None:
                raise ConflictError("Current execution contract is missing")
            old_tasks = {task.id: task for task in current.tasks}
            revised_tasks = {task.id: task for task in plan.tasks}
            if any(revised_tasks.get(key) != task for key, task in old_tasks.items()):
                raise PolicyDeniedError(
                    "Repair plans cannot remove or rewrite existing task history"
                )
            if not set(current.dependencies) <= set(plan.dependencies):
                raise PolicyDeniedError("Repair plans cannot remove existing dependencies")
            if any(
                edge.task_id in old_tasks
                for edge in set(plan.dependencies) - set(current.dependencies)
            ):
                raise PolicyDeniedError("Revisions cannot change dependencies of existing tasks")
            added = tuple(task for task in plan.tasks if task.id not in old_tasks)
            if not added or any(
                task.status != TaskStatus.PENDING
                or task.attempt_count
                or task.plan_version != plan.version
                for task in added
            ):
                raise ConflictError("Repair additions must be new unexecuted tasks")
            if any(
                task.status in {TaskStatus.RUNNING, TaskStatus.WAITING, TaskStatus.BLOCKED}
                for task in current.tasks
            ):
                raise ConflictError("Active tasks must reach a terminal checkpoint before repair")
            ids = {item.id for item in goal.criteria}
            if any(not set(task.acceptance_criterion_ids) <= ids for task in added):
                raise ConflictError("Repair tasks reference criteria outside the accepted goal")
            if safe_diagnostic(plan.model_dump_json()) != plan.model_dump_json():
                raise PolicyDeniedError("Unsafe repair plan content")
            uow.runtime.save_plan(plan)
            updated = run.model_copy(
                update={
                    "plan_version": plan.version,
                    "repair_iteration": run.repair_iteration + int(repair),
                }
            )
            uow.runs.save(updated)
            at = self.clock()
            emit(
                uow,
                updated,
                EventType.PLAN_REVISED,
                f"{key}:revised",
                at,
                EventPayload(
                    plan_version=plan.version,
                    goal_version_id=plan.goal_version_id,
                    task_ids=tuple(task.id for task in added),
                ),
            )
            if repair:
                emit(
                    uow,
                    updated,
                    EventType.REPAIR_STARTED,
                    f"{key}:started",
                    at,
                    EventPayload(plan_version=plan.version),
                )
            for task in added:
                emit(
                    uow,
                    updated,
                    EventType.TASK_CREATED,
                    f"{key}:task:{task.id}",
                    at,
                    EventPayload(status=task.status),
                    task_id=task.id,
                )
            refresh_ready(uow, updated, key, at)
            uow.commit()
            return locked_run(uow, run.id)
