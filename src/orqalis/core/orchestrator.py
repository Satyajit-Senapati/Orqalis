from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid5

from orqalis.core.approval_guard import require_approval, require_delivery_binding
from orqalis.core.approval_subjects import goal_subject, plan_subject, repair_subject
from orqalis.core.phases import update_phase
from orqalis.core.plan_revision import PlanRevisionService
from orqalis.core.planning import plan_identity
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import (
    emit,
    locked_run,
    orchestrator_actor,
    require_key,
    set_actor_status,
)
from orqalis.core.state_machine import PHASES, TERMINAL, validate_transition
from orqalis.core.task_runtime import TaskRuntime, refresh_ready
from orqalis.domain.acceptance import AcceptanceStatus
from orqalis.domain.agent import ActorStatus, AgentRole
from orqalis.domain.approval import ApprovalStage
from orqalis.domain.base import utc_now
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.plan import TaskPlan
from orqalis.domain.run import Run, RunState
from orqalis.domain.task import Task, TaskDependency, TaskExecution, TaskStatus
from orqalis.observability.instrumentation import observed
from orqalis.security.redaction import safe_diagnostic

_SUSPENDED = {RunState.PAUSED, RunState.BLOCKED, RunState.HUMAN_REVIEW_REQUIRED}


class Orchestrator:
    """Authoritative lifecycle entry point. Workers return results; they do not call transitions."""

    def __init__(
        self, unit_of_work: Callable[[], ProjectUnitOfWork], clock: Callable[[], datetime] = utc_now
    ) -> None:
        self.unit_of_work, self.clock = unit_of_work, clock
        self._tasks = TaskRuntime(unit_of_work, clock)

    def install_plan(self, plan: TaskPlan, key: str) -> Run:
        require_key(key)
        with self.unit_of_work() as uow:
            run = locked_run(uow, plan.run_id)
            preparation = tuple(t for t in uow.runtime.tasks(run.id) if t.plan_version == 0)
            if preparation and not any(t.plan_version == 0 for t in plan.tasks):
                if any(t.status != TaskStatus.SUCCEEDED for t in preparation):
                    raise ConflictError("Preparatory tasks must complete before planning")
                roots = [
                    t for t in plan.tasks if not any(e.task_id == t.id for e in plan.dependencies)
                ]
                plan = plan.model_copy(
                    update={
                        "tasks": (*preparation, *plan.tasks),
                        "dependencies": (
                            *plan.dependencies,
                            *(
                                TaskDependency(task_id=t.id, depends_on_task_id=p.id)
                                for t in roots
                                for p in preparation
                            ),
                        ),
                    }
                )
            if any(t.plan_version == 0 and t not in preparation for t in plan.tasks):
                raise ConflictError("Preparatory task history must match persisted records")
            plan = TaskPlan.model_validate(plan.model_dump())
            if uow.events.by_key(run.id, f"{key}:plan"):
                stored = uow.runtime.get_plan(run.id, plan.version)

                if not stored or plan_identity(stored) != plan_identity(plan):
                    raise ConflictError("Idempotency key belongs to another plan")
                return run
            if run.state != RunState.GOAL_DEFINED or run.plan_version != 0:
                raise ConflictError("Initial planning requires GOAL_DEFINED and no current plan")
            if plan.goal_version_id != run.current_goal_version_id or plan.version != 1:
                raise ConflictError("Plan must reference the current goal and initial plan version")
            if any(
                (task.status != TaskStatus.PENDING or task.attempt_count)
                and task not in preparation
                for task in plan.tasks
            ):
                raise ConflictError("Planner cannot assert execution outcomes")
            if safe_diagnostic(plan.model_dump_json()) != plan.model_dump_json():
                raise PolicyDeniedError("Unsafe plan content")
            contract = uow.runs.get_goal(plan.goal_version_id)
            if contract is None:
                raise ConflictError("Goal not found")
            ids = {criterion.id for criterion in contract.criteria}
            affected = {
                criterion for task in plan.tasks for criterion in task.acceptance_criterion_ids
            }
            if (
                not affected <= ids
                or not {
                    criterion.id
                    for criterion in contract.criteria
                    if criterion.priority == "required"
                }
                <= affected
            ):
                raise ConflictError(
                    "Plan must cover required criteria and reference only this goal"
                )
            require_approval(
                uow,
                run,
                ApprovalStage.GOAL,
                contract.goal.version,
                goal_subject(contract),
                "Approve goal before planning",
            )
            uow.runtime.save_plan(plan)
            run = run.model_copy(update={"plan_version": plan.version})
            uow.runs.save(run)
            at = self.clock()
            emit(
                uow,
                run,
                EventType.PLAN_CREATED,
                f"{key}:plan",
                at,
                EventPayload(
                    plan_version=plan.version,
                    goal_version_id=plan.goal_version_id,
                    task_ids=tuple(task.id for task in plan.tasks),
                ),
            )
            for task in plan.tasks:
                if task in preparation:
                    continue
                emit(
                    uow,
                    run,
                    EventType.TASK_CREATED,
                    f"{key}:created:{task.id}",
                    at,
                    EventPayload(status=task.status),
                    task_id=task.id,
                )
            refresh_ready(uow, run, key, at)
            uow.commit()
            return locked_run(uow, run.id)

    def install_revised_goal_plan(self, plan: TaskPlan, key: str) -> Run:
        from orqalis.core.replanning import GoalReplanning

        return GoalReplanning(self.unit_of_work).install(plan, key)

    def replace_preview_plan(self, plan: TaskPlan, expected_version: int, key: str) -> Run:
        from orqalis.core.preview_revision import PreviewRevisionService

        return PreviewRevisionService(self.unit_of_work, self.clock).replace(
            plan, expected_version, key
        )

    def install_repair_plan(self, plan: TaskPlan, key: str) -> Run:
        return PlanRevisionService(self.unit_of_work, self.clock).install_repair(plan, key)

    def install_delivery_plan(self, plan: TaskPlan, key: str) -> Run:
        return PlanRevisionService(self.unit_of_work, self.clock).install_delivery(plan, key)

    @observed("orchestrator.advance")
    def advance(self, run_id: UUID, target: RunState, key: str) -> Run:
        require_key(key)
        with self.unit_of_work() as uow:
            run = locked_run(uow, run_id)
            existing = uow.events.by_key(run_id, f"{key}:run")
            if existing:
                if existing.payload.status != target:
                    raise ConflictError("Idempotency key belongs to another transition")
                return run
            validate_transition(run.state, target, run.resume_state)
            self._guard(uow, run, target)
            at = self.clock()
            actor = orchestrator_actor(uow, run, at)
            if target in TERMINAL:
                self._cancel_pending(uow, run, key, at)
                actor = orchestrator_actor(uow, run, at)
            previous = run.state
            resume_state = run.resume_state
            if target in _SUSPENDED and previous not in _SUSPENDED:
                resume_state = previous
            elif previous in _SUSPENDED and target not in _SUSPENDED:
                resume_state = None
            run = run.model_copy(
                update={
                    "state": target,
                    "ui_phase": PHASES.get(target, run.ui_phase),
                    "resume_state": resume_state,
                    "started_at": run.started_at or (at if target not in TERMINAL else None),
                    "completed_at": at if target in TERMINAL else None,
                }
            )
            uow.runs.save(run)
            kind = {
                RunState.PAUSED: EventType.RUN_PAUSED,
                RunState.BLOCKED: EventType.RUN_BLOCKED,
                RunState.HUMAN_REVIEW_REQUIRED: EventType.RUN_BLOCKED,
                RunState.CANCELLED: EventType.RUN_CANCELLED,
                RunState.FAILED: EventType.RUN_FAILED,
                RunState.COMPLETED: EventType.RUN_COMPLETED,
            }.get(
                target,
                EventType.RUN_RESUMED
                if previous in _SUSPENDED
                else EventType.RUN_STARTED
                if previous == RunState.RECEIVED
                else EventType.RUN_STATE_CHANGED,
            )
            event = emit(
                uow,
                run,
                kind,
                f"{key}:run",
                at,
                EventPayload(previous_status=previous, status=target),
                actor.id,
            )
            actor_status = (
                ActorStatus.CANCELLED
                if target == RunState.CANCELLED
                else ActorStatus.FAILED
                if target == RunState.FAILED
                else ActorStatus.COMPLETE
                if target == RunState.COMPLETED
                else ActorStatus.WAITING_FOR_DEPENDENCY
                if target == RunState.PAUSED
                else ActorStatus.BLOCKED
                if target in _SUSPENDED
                else ActorStatus.WORKING
            )
            set_actor_status(
                uow, run, actor, actor_status, f"{key}:orchestrator", event.occurred_at
            )
            phase_status = (
                TaskStatus.CANCELLED
                if target == RunState.CANCELLED
                else TaskStatus.FAILED
                if target == RunState.FAILED
                else TaskStatus.SUCCEEDED
                if target == RunState.COMPLETED
                else TaskStatus.WAITING
                if target == RunState.PAUSED
                else TaskStatus.BLOCKED
                if target in _SUSPENDED
                else TaskStatus.RUNNING
            )
            update_phase(uow, run, key, event.occurred_at, phase_status, target in TERMINAL)
            uow.commit()
            return locked_run(uow, run_id)

    def _guard(self, uow: ProjectUnitOfWork, run: Run, target: RunState) -> None:
        from orqalis.delivery.gates import guard_delivery

        guard_delivery(uow, run, target)
        if target == RunState.CHANGE_GUARD:
            require_delivery_binding(uow, run)
        if target == RunState.REPAIR_PLANNING:
            reviews = uow.execution.reviews(run.id)
            failed = reviews[-1] if reviews else None
            if (
                failed is None
                or failed.result.overall != "FAIL"
                or failed.plan_version != run.plan_version
                or failed.goal_version_id != run.current_goal_version_id
            ):
                raise ConflictError("Repair planning requires the current failed review")
            require_approval(
                uow,
                run,
                ApprovalStage.REPAIR,
                run.plan_version,
                repair_subject(failed),
                "Review failed evidence before targeted repair",
            )
        if target == RunState.EXECUTING and run.state == RunState.REPAIR_PLANNING:
            reviews = uow.execution.reviews(run.id)
            failed = reviews[-1] if reviews else None
            if failed is None or run.plan_version != failed.plan_version + 1:
                raise ConflictError("Repair plan must be installed before execution")
        if target in _SUSPENDED and any(
            attempt.status == TaskStatus.RUNNING for attempt in uow.runtime.executions(run.id)
        ):
            raise ConflictError("Workers must reach a waiting checkpoint before suspending the run")
        if target == RunState.GOAL_DEFINED and run.current_goal_version_id is None:
            raise ConflictError("A versioned goal is required")
        if target in {RunState.PLANNED, RunState.EXECUTING}:
            plan = uow.runtime.get_plan(run.id, run.plan_version)
            if not plan or plan.goal_version_id != run.current_goal_version_id:
                raise ConflictError("A valid plan for the current goal is required")
            if target == RunState.EXECUTING:
                require_approval(
                    uow,
                    run,
                    ApprovalStage.PLAN,
                    run.plan_version,
                    plan_subject(plan),
                    "Approve dependency plan before execution",
                )
        if target == RunState.CHANGE_GUARD:
            contract = (
                uow.runs.get_goal(run.current_goal_version_id)
                if run.current_goal_version_id
                else None
            )
            if not contract or any(
                item.status != AcceptanceStatus.PASS
                for item in contract.criteria
                if item.priority == "required"
            ):
                raise ConflictError("Required acceptance criteria must pass before Change Guardian")

    def _cancel_pending(self, uow: ProjectUnitOfWork, run: Run, key: str, at: datetime) -> None:
        for attempt in uow.runtime.executions(run.id):
            if attempt.status in {TaskStatus.RUNNING, TaskStatus.WAITING, TaskStatus.BLOCKED}:
                self._tasks.transition_in_transaction(
                    uow, run, attempt.id, TaskStatus.CANCELLED, f"{key}:{attempt.id}", at
                )
        plan = uow.runtime.get_plan(run.id, run.plan_version)
        if plan:
            for task in plan.tasks:
                if task.status in {TaskStatus.PENDING, TaskStatus.READY}:
                    uow.runtime.save_task(
                        task.model_copy(
                            update={
                                "status": TaskStatus.CANCELLED,
                                "completed_at": at,
                            }
                        )
                    )
                    emit(
                        uow,
                        run,
                        EventType.TASK_CANCELLED,
                        f"{key}:cancel:{task.id}",
                        at,
                        EventPayload(status=TaskStatus.CANCELLED),
                        task_id=task.id,
                    )

    @observed("orchestrator.start_task")
    def start_requirements(self, run_id: UUID) -> TaskExecution:
        with self.unit_of_work() as uow:
            run = locked_run(uow, run_id)
            if run.state != RunState.ANALYZING or run.plan_version:
                raise ConflictError("Requirements work requires the analyzing checkpoint")
            task_id = uuid5(run_id, "requirements-task")
            task = next((t for t in uow.runtime.tasks(run_id) if t.id == task_id), None)
            if task is None:
                at = self.clock()
                task = Task(
                    id=task_id,
                    run_id=run_id,
                    plan_version=0,
                    description=run.request,
                    expected_outcome="A scoped goal with testable criteria and definition of done",
                    preferred_role=AgentRole.REQUIREMENTS,
                    validation_method="GoalDraft schema and immutable versioned contract",
                    status=TaskStatus.READY,
                    ready_at=at,
                    created_at=at,
                )
                uow.runtime.add_task(task)
                for kind in (EventType.TASK_CREATED, EventType.TASK_READY):
                    emit(
                        uow,
                        run,
                        kind,
                        f"requirements:{kind}",
                        at,
                        EventPayload(status=task.status),
                        task_id=task.id,
                    )
                uow.commit()
            attempts = tuple(a for a in uow.runtime.executions(run_id) if a.task_id == task.id)
            if attempts and attempts[-1].status in {TaskStatus.RUNNING, TaskStatus.SUCCEEDED}:
                return attempts[-1]
        return self._tasks.start(run_id, task_id, f"requirements:attempt:{task.attempt_count + 1}")

    def start_task(self, run_id: UUID, task_id: UUID, key: str) -> TaskExecution:
        return self._tasks.start(run_id, task_id, key)

    @observed("orchestrator.transition_task")
    def transition_task(
        self, run_id: UUID, execution_id: UUID, status: TaskStatus, key: str
    ) -> TaskExecution:
        return self._tasks.transition(run_id, execution_id, status, key)

    @observed("orchestrator.recover_task")
    def recover_task(
        self,
        run_id: UUID,
        execution_id: UUID,
        reason: str,
        key: str,
        *,
        acknowledge_uncertainty: bool = False,
    ) -> "Task":
        from orqalis.core.recovery import RecoveryService

        return RecoveryService(self.unit_of_work).retry(
            run_id,
            execution_id,
            reason,
            key,
            acknowledge_uncertainty=acknowledge_uncertainty,
        )

    def resume(self, run_id: UUID, key: str) -> Run:
        with self.unit_of_work() as uow:
            run = locked_run(uow, run_id)
            if run.resume_state is None:
                existing = uow.events.by_key(run_id, f"{key}:run")
                if existing and existing.event_type == EventType.RUN_RESUMED:
                    return run
                raise ConflictError("Run has no suspended state to resume")
            target = run.resume_state
        return self.advance(run_id, target, key)
