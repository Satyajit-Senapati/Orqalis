from collections.abc import Callable
from uuid import UUID, uuid5

from orqalis.core.orchestrator import Orchestrator
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit, locked_run
from orqalis.domain.agent import AgentRole
from orqalis.domain.base import utc_now
from orqalis.domain.errors import ConflictError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.execution import ReviewRecord
from orqalis.domain.plan import TaskPlan
from orqalis.domain.run import RunState
from orqalis.domain.task import Task, TaskDependency


class RepairPlanner:
    def plan(
        self, current: TaskPlan, review: ReviewRecord, criterion_ids: tuple[UUID, ...]
    ) -> TaskPlan:
        failed = tuple(
            item.criterion_id for item in review.result.criteria if item.status == "FAIL"
        )
        affected = failed or criterion_ids
        reasons = "; ".join(item.reason for item in review.result.criteria if item.status == "FAIL")
        reasons = reasons or "; ".join(review.result.blocking_findings)
        version = current.version + 1
        diagnosis = Task(
            id=uuid5(current.run_id, f"repair:{version}:diagnose"),
            run_id=current.run_id,
            plan_version=version,
            description=f"Diagnose failed acceptance: {reasons}",
            expected_outcome="Identify the smallest correction and affected source files",
            preferred_role=AgentRole.REPAIR,
            required_capabilities=("diagnosis",),
            validation_method="Source-backed diagnosis",
            acceptance_criterion_ids=affected,
        )
        original = next(
            (
                task
                for task in current.tasks
                if task.preferred_role == AgentRole.DEVELOPER
                and set(task.acceptance_criterion_ids) & set(affected)
            ),
            None,
        )
        implementation = Task(
            id=uuid5(current.run_id, f"repair:{version}:implement"),
            run_id=current.run_id,
            plan_version=version,
            parent_task_id=original.id if original else None,
            description=f"Repair only the affected behavior: {reasons}",
            expected_outcome="Resolve failed criteria without changing the accepted goal",
            preferred_role=AgentRole.DEVELOPER,
            required_capabilities=tuple(
                dict.fromkeys(
                    ("implementation", *(original.required_capabilities if original else ()))
                )
            ),
            validation_method="Affected checks and required regression suite",
            acceptance_criterion_ids=affected,
        )
        test = Task(
            id=uuid5(current.run_id, f"repair:{version}:test"),
            run_id=current.run_id,
            plan_version=version,
            description="Retest repaired behavior and required regressions",
            expected_outcome="Current evidence for the complete acceptance contract",
            preferred_role=AgentRole.TESTER,
            validation_method="Acceptance validators",
            acceptance_criterion_ids=criterion_ids,
        )
        reviewer = Task(
            id=uuid5(current.run_id, f"repair:{version}:review"),
            run_id=current.run_id,
            plan_version=version,
            description="Review the repaired implementation and regression evidence",
            expected_outcome="Independent criterion-by-criterion review",
            preferred_role=AgentRole.REVIEWER,
            required_capabilities=("evidence_review",),
            validation_method="Structured acceptance review",
            acceptance_criterion_ids=criterion_ids,
        )
        added = (diagnosis, implementation, test, reviewer)
        edges = tuple(
            TaskDependency(task_id=child.id, depends_on_task_id=parent.id)
            for parent, child in zip(added, added[1:], strict=False)
        )
        return TaskPlan(
            run_id=current.run_id,
            goal_version_id=current.goal_version_id,
            version=version,
            tasks=(*current.tasks, *added),
            dependencies=(*current.dependencies, *edges),
        )


class RepairCoordinator:
    def __init__(
        self, factory: Callable[[], ProjectUnitOfWork], orchestrator: Orchestrator
    ) -> None:
        self.factory, self.orchestrator = factory, orchestrator

    def schedule(self, run_id: UUID) -> bool:
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            records = uow.execution.reviews(run_id)
            review = records[-1] if records else None
            plan = uow.runtime.get_plan(run_id, run.plan_version)
            goal = (
                uow.runs.get_goal(run.current_goal_version_id)
                if run.current_goal_version_id
                else None
            )
            if review is None or plan is None or goal is None or review.result.overall != "FAIL":
                raise ConflictError("Targeted repair requires a persisted failed review")
            if review.goal_version_id != run.current_goal_version_id:
                raise ConflictError("Review belongs to another goal version")
            key = f"repair:{review.id}"
            if (
                run.state == RunState.REPAIR_PLANNING
                and run.plan_version == review.plan_version + 1
            ):
                installed = True
            elif run.plan_version == review.plan_version:
                installed = False
            else:
                raise ConflictError("Review does not match the current plan")
            limit_key = f"{key}:limit:{run.last_event_sequence}"
            if not installed and run.repair_iteration >= run.max_repair_iterations:
                emit(
                    uow,
                    run,
                    EventType.REPAIR_REQUESTED,
                    f"{key}:limit",
                    utc_now(),
                    EventPayload(status="LIMIT_REACHED", reason="Configured repair limit reached"),
                )
                uow.commit()
                limit = True
            else:
                limit = False
        if limit:
            self.orchestrator.advance(run_id, RunState.HUMAN_REVIEW_REQUIRED, limit_key)
            return False
        if not installed:
            with self.factory() as uow:
                current_run = locked_run(uow, run_id)
                emit(
                    uow,
                    current_run,
                    EventType.REPAIR_REQUESTED,
                    f"{key}:request",
                    utc_now(),
                    EventPayload(
                        plan_version=plan.version, reason="Failed review requires targeted repair"
                    ),
                )
                uow.commit()
            if run.state == RunState.REVIEWING:
                self.orchestrator.advance(run_id, RunState.REPAIR_PLANNING, f"{key}:planning")
            elif run.state != RunState.REPAIR_PLANNING:
                raise ConflictError("Run is not at a repair planning checkpoint")
            revised = RepairPlanner().plan(plan, review, tuple(item.id for item in goal.criteria))
            self.orchestrator.install_repair_plan(revised, f"{key}:plan")
        self.orchestrator.advance(run_id, RunState.EXECUTING, f"{key}:execute")
        return True
