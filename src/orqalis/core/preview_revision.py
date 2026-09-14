from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from orqalis.core.planning import plan_identity
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit, locked_run, require_key
from orqalis.core.task_runtime import refresh_ready
from orqalis.domain.agent import AgentRole
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.plan import TaskPlan
from orqalis.domain.run import Run, RunState
from orqalis.domain.task import Task, TaskDependency, TaskStatus
from orqalis.security.redaction import safe_diagnostic


class PreviewRevisionService:
    """Orchestrator-owned replacement of work that has not begun execution."""

    def __init__(
        self, factory: Callable[[], ProjectUnitOfWork], clock: Callable[[], datetime]
    ) -> None:
        self.factory, self.clock = factory, clock

    def replace(self, plan: TaskPlan, expected_version: int, key: str) -> Run:
        require_key(key)
        plan = TaskPlan.model_validate(plan.model_dump())
        with self.factory() as lease:
            if not lease.execution.try_run_lock(plan.run_id):
                raise ConflictError("A worker owns this run")
            with self.factory() as uow:
                run = locked_run(uow, plan.run_id)
                prior = uow.events.by_key(run.id, f"preview-edit:{key}")
                if prior:
                    stored = uow.runtime.get_plan(run.id, plan.version)
                    prepared = (
                        tuple(t for t in stored.tasks if t.plan_version == 0) if stored else ()
                    )
                    expected = self._with_preparation(plan, prepared)
                    if not stored or plan_identity(stored) != plan_identity(expected):
                        raise ConflictError("Plan edit key belongs to another plan")
                    return run
                if not (
                    run.state == RunState.PLANNED
                    or run.state == RunState.PAUSED
                    and run.resume_state == RunState.PLANNED
                ):
                    raise ConflictError("Plan edits require an unexecuted PLANNED checkpoint")
                if run.plan_version != expected_version or plan.version != expected_version + 1:
                    raise ConflictError("Plan edit uses a stale expected version")
                if plan.goal_version_id != run.current_goal_version_id:
                    raise ConflictError("Plan edit must preserve the current goal version")
                if uow.execution.workspace(run.id) is not None:
                    raise ConflictError("Plan cannot be edited after workspace creation")
                planned_ids = {
                    task.id for task in uow.runtime.tasks(run.id) if task.plan_version > 0
                }
                if any(
                    attempt.task_id in planned_ids for attempt in uow.runtime.executions(run.id)
                ):
                    raise ConflictError("Plan cannot be edited after execution begins")
                current = uow.runtime.get_plan(run.id, expected_version)
                goal = uow.runs.get_goal(plan.goal_version_id)
                if current is None or goal is None:
                    raise ConflictError("Current plan or goal is missing")
                if current.goal_version_id != run.current_goal_version_id:
                    raise ConflictError("Goal changed; use the goal replanning path")
                history = {task.id for task in uow.runtime.tasks(run.id)}
                if any(
                    task.id in history
                    or task.plan_version != plan.version
                    or task.status != TaskStatus.PENDING
                    or task.attempt_count
                    or task.ready_at is not None
                    or task.started_at is not None
                    or task.completed_at is not None
                    for task in plan.tasks
                ):
                    raise ConflictError("Edited tasks need fresh, unexecuted identities")
                self._validate_roles(plan)
                criteria = {criterion.id for criterion in goal.criteria}
                covered = {item for task in plan.tasks for item in task.acceptance_criterion_ids}
                required = {item.id for item in goal.criteria if item.priority == "required"}
                if not covered <= criteria or not required <= covered:
                    raise ConflictError("Plan must cover only this goal's required criteria")
                prepared = tuple(task for task in current.tasks if task.plan_version == 0)
                revised = TaskPlan.model_validate(
                    self._with_preparation(plan, prepared).model_dump()
                )
                if safe_diagnostic(revised.model_dump_json()) != revised.model_dump_json():
                    raise PolicyDeniedError("Unsafe plan content")
                at = self.clock()
                for task in current.tasks:
                    if task.plan_version == 0:
                        continue
                    if task.status not in {TaskStatus.PENDING, TaskStatus.READY}:
                        raise ConflictError("Only unexecuted tasks may be superseded")
                    uow.runtime.save_task(
                        task.model_copy(update={"status": TaskStatus.CANCELLED, "completed_at": at})
                    )
                    emit(
                        uow,
                        run,
                        EventType.TASK_CANCELLED,
                        f"preview-edit:{key}:cancel:{task.id}",
                        at,
                        EventPayload(status=TaskStatus.CANCELLED, reason="Operator edited plan"),
                        task_id=task.id,
                    )
                uow.runtime.save_plan(revised)
                updated = run.model_copy(update={"plan_version": revised.version})
                uow.runs.save(updated)
                emit(
                    uow,
                    updated,
                    EventType.PLAN_REVISED,
                    f"preview-edit:{key}",
                    at,
                    EventPayload(
                        plan_version=revised.version,
                        goal_version_id=revised.goal_version_id,
                        task_ids=tuple(task.id for task in plan.tasks),
                        reason="Operator edited plan before execution",
                    ),
                )
                for task in plan.tasks:
                    emit(
                        uow,
                        updated,
                        EventType.TASK_CREATED,
                        f"preview-edit:{key}:task:{task.id}",
                        at,
                        EventPayload(status=task.status),
                        task_id=task.id,
                    )
                refresh_ready(uow, updated, f"preview-edit:{key}", at)
                uow.commit()
                return locked_run(uow, run.id)

    @staticmethod
    def _with_preparation(plan: TaskPlan, prepared: tuple[Task, ...]) -> TaskPlan:
        if not prepared:
            return plan
        roots = [
            task
            for task in plan.tasks
            if not any(edge.task_id == task.id for edge in plan.dependencies)
        ]
        return plan.model_copy(
            update={
                "tasks": (*prepared, *plan.tasks),
                "dependencies": (
                    *plan.dependencies,
                    *(
                        TaskDependency(task_id=task.id, depends_on_task_id=prior.id)
                        for task in roots
                        for prior in prepared
                    ),
                ),
            }
        )

    @staticmethod
    def _validate_roles(plan: TaskPlan) -> None:
        # The current executor runs role waves in this order. Reject DAGs it
        # cannot execute faithfully rather than offering a misleading edit.
        rank = {AgentRole.DEVELOPER: 0, AgentRole.TESTER: 1, AgentRole.REVIEWER: 2}
        roles = {task.preferred_role for task in plan.tasks}
        if roles != set(rank):
            raise ConflictError("Preview requires Developer, Tester and Reviewer tasks")
        by_id = {task.id: task for task in plan.tasks}
        if any(
            rank[by_id[edge.depends_on_task_id].preferred_role]
            > rank[by_id[edge.task_id].preferred_role]
            for edge in plan.dependencies
        ):
            raise ConflictError("Plan dependencies cannot reverse execution role order")
        prerequisites: dict[UUID, set[UUID]] = {task.id: set() for task in plan.tasks}
        for edge in plan.dependencies:
            prerequisites[edge.task_id].add(edge.depends_on_task_id)

        def ancestors(task_id: UUID) -> set[UUID]:
            seen: set[UUID] = set()
            pending = list(prerequisites[task_id])
            while pending:
                parent = pending.pop()
                if parent not in seen:
                    seen.add(parent)
                    pending.extend(prerequisites[parent])
            return seen

        developers = {task.id for task in plan.tasks if task.preferred_role == AgentRole.DEVELOPER}
        testers = {task.id for task in plan.tasks if task.preferred_role == AgentRole.TESTER}
        for task in plan.tasks:
            required = (
                developers
                if task.preferred_role == AgentRole.TESTER
                else testers
                if task.preferred_role == AgentRole.REVIEWER
                else set()
            )
            if not required <= ancestors(task.id):
                raise ConflictError("Plan dependencies must preserve execution role waves")
