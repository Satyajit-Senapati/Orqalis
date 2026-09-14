import asyncio
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from orqalis.agents.roles import provider_output_schema
from orqalis.core.approval_subjects import goal_subject, plan_subject, repair_subject
from orqalis.core.approvals import ApprovalService
from orqalis.core.goals import GoalService
from orqalis.core.orchestrator import Orchestrator
from orqalis.core.plan_preview import PlanPreviewService
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.repair import RepairCoordinator
from orqalis.core.runtime_support import emit, locked_run
from orqalis.core.scheduler import ordered_tasks, ready_tasks
from orqalis.core.vertical_plan import VerticalPlanner
from orqalis.domain.agent import AgentRole
from orqalis.domain.approval import ApprovalStage, ApprovalStatus
from orqalis.domain.base import utc_now
from orqalis.domain.errors import ConflictError, NotFoundError, OrqalisError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.execution import ExecutionPolicy, ExecutionSummary, ReviewResult, WorkerResult
from orqalis.domain.memory import ContextPack
from orqalis.domain.run import RunState
from orqalis.domain.task import Task, TaskExecution, TaskStatus
from orqalis.execution.artifacts import record_artifacts
from orqalis.execution.cancellation import at_checkpoint, watch_cancellation
from orqalis.execution.evaluator import WorkspaceEvaluator
from orqalis.execution.review import ReviewService, workspace_digest
from orqalis.execution.worker import AgentWorker
from orqalis.execution.workspaces import ExecutionWorkspaces
from orqalis.memory.service import MemoryService
from orqalis.observability.instrumentation import observed_async


class RunExecutor:
    """Deterministic application driver. Workers return results to Orchestrator."""

    def __init__(
        self,
        factory: Callable[[], ProjectUnitOfWork],
        orchestrator: Orchestrator,
        goals: GoalService,
        memory: MemoryService,
        workspaces: ExecutionWorkspaces,
        worker: AgentWorker,
        reviews: ReviewService,
        approvals: ApprovalService | None = None,
        plans: PlanPreviewService | None = None,
    ) -> None:
        self.factory, self.orchestrator, self.goals, self.memory = (
            factory,
            orchestrator,
            goals,
            memory,
        )
        self.workspaces, self.worker, self.reviews = workspaces, worker, reviews
        self.repair = RepairCoordinator(factory, orchestrator)
        self.approvals = approvals or ApprovalService(factory)
        self.plans = plans

    @observed_async("run.execute")
    async def execute(
        self,
        run_id: UUID,
        provider_id: str,
        policy: ExecutionPolicy,
        *,
        repair_automatically: bool = True,
    ) -> ExecutionSummary:
        with self.factory() as lease:
            if not lease.execution.try_run_lock(run_id):
                raise ConflictError("Another Orchestrator worker owns this run")
            while True:
                with self.factory() as uow:
                    checkpoint = locked_run(uow, run_id)
                if checkpoint.state == RunState.REPAIR_PLANNING:
                    self._require_repair(run_id)
                    self.repair.schedule(run_id)
                result = await watch_cancellation(
                    self.factory, run_id, self._execute_locked(run_id, provider_id, policy)
                )
                if result.review:
                    with self.factory() as uow:
                        finished = locked_run(uow, run_id)
                        if finished.repair_iteration:
                            emit(
                                uow,
                                finished,
                                EventType.REPAIR_COMPLETED,
                                f"repair-completed:{result.review.id}",
                                utc_now(),
                                EventPayload(
                                    plan_version=finished.plan_version,
                                    status=result.review.result.overall,
                                ),
                            )
                            uow.commit()
                if result.review is None or result.review.result.overall == "PASS":
                    return result
                with self.factory() as uow:
                    current = locked_run(uow, run_id)
                if current.repair_iteration < current.max_repair_iterations:
                    self._require_repair(run_id)
                if not self.repair.schedule(run_id):
                    return result.model_copy(update={"state": RunState.HUMAN_REVIEW_REQUIRED})
                if not repair_automatically:
                    return result.model_copy(update={"state": RunState.EXECUTING})

    def _require_repair(self, run_id: UUID) -> None:
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            reviews = uow.execution.reviews(run_id)
            review = reviews[-1] if reviews else None
            if review is None or review.result.overall != "FAIL":
                raise ConflictError("Repair approval requires a persisted failed review")
            if (
                run.plan_version == review.plan_version + 1
                and run.state == RunState.REPAIR_PLANNING
            ):
                return  # Approval was checked before the repair plan was installed.
            version = review.plan_version
        requested = self.approvals.ensure(
            run_id,
            ApprovalStage.REPAIR,
            version,
            repair_subject(review),
            "Review the failed evidence before a targeted repair",
        )
        if requested is not None and requested.status != ApprovalStatus.APPROVED:
            raise PolicyDeniedError(f"Repair approval required: {requested.id}")

    async def _execute_locked(
        self,
        run_id: UUID,
        provider_id: str,
        policy: ExecutionPolicy,
        *,
        repair_automatically: bool = True,
    ) -> ExecutionSummary:
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            project = uow.projects.get(run.project_id)
            if project is None:
                raise NotFoundError("Project not found")
            if run.state not in {
                RunState.GOAL_DEFINED,
                RunState.PLANNED,
                RunState.EXECUTING,
                RunState.INTEGRATING,
                RunState.TESTING,
                RunState.REVIEWING,
            }:
                raise ConflictError("Run is not at an executable checkpoint")
        if provider_id != "auto" and provider_id not in self.worker.agents.router.providers:
            raise PolicyDeniedError("Requested provider is not configured")
        if run.state == RunState.GOAL_DEFINED:
            if self.plans is not None:
                self.plans.preview(run_id, "vertical")
            else:
                contract = self.goals.get(run_id)
                requested = self.approvals.ensure(
                    run_id,
                    ApprovalStage.GOAL,
                    contract.goal.version,
                    goal_subject(contract),
                    "Review goal before planning",
                )
                if requested is not None and requested.status != ApprovalStatus.APPROVED:
                    raise PolicyDeniedError(f"Goal approval required: {requested.id}")
                context_before_workspace = self.memory.context(project, run.request)
                self.orchestrator.install_plan(
                    VerticalPlanner().plan(self.goals.get(run_id), context_before_workspace),
                    "vertical:plan",
                )
                self.orchestrator.advance(run_id, RunState.PLANNED, "vertical:planned")
        with self.factory() as uow:
            prepared = locked_run(uow, run_id)
            plan = uow.runtime.get_plan(run_id, prepared.plan_version)
            if plan is None:
                raise NotFoundError("Current plan not found")
        requested = self.approvals.ensure(
            run_id,
            ApprovalStage.PLAN,
            prepared.plan_version,
            plan_subject(plan),
            "Review the dependency plan before execution",
        )
        if requested is not None and requested.status != ApprovalStatus.APPROVED:
            raise PolicyDeniedError(f"Plan approval required: {requested.id}")
        workspace = self.workspaces.ensure(run_id, policy)
        context = self.memory.context(
            project.model_copy(update={"repo_root": workspace.path}), run.request
        )
        with self.factory() as uow:
            current = locked_run(uow, run_id)
        if current.state == RunState.PLANNED:
            self.orchestrator.advance(
                run_id, RunState.EXECUTING, f"vertical:{current.plan_version}:executing"
            )
        await self._context_wave(run_id, provider_id, context, policy)
        for role in (AgentRole.REPAIR, AgentRole.DEVELOPER, AgentRole.TESTER, AgentRole.REVIEWER):
            with self.factory() as uow:
                current = locked_run(uow, run_id)
                plan = uow.runtime.get_plan(run_id, current.plan_version)
                if plan is None:
                    raise NotFoundError("Current plan not found")
                tasks = tuple(task for task in ordered_tasks(plan) if task.preferred_role == role)
            if not tasks and role == AgentRole.REPAIR:
                continue
            if not tasks:
                raise ConflictError(
                    "Vertical execution requires developer, tester and reviewer tasks"
                )
            for task in tasks:
                if task.status == TaskStatus.SUCCEEDED:
                    continue
                if task.status in {TaskStatus.FAILED, TaskStatus.BLOCKED, TaskStatus.CANCELLED}:
                    raise ConflictError("Task requires explicit repair or recovery")
                if role == AgentRole.TESTER and current.state == RunState.EXECUTING:
                    self.orchestrator.advance(
                        run_id, RunState.INTEGRATING, f"vertical:{current.plan_version}:integrate"
                    )
                    self.orchestrator.advance(
                        run_id, RunState.TESTING, f"vertical:{current.plan_version}:test"
                    )
                elif role == AgentRole.TESTER and current.state == RunState.INTEGRATING:
                    self.orchestrator.advance(
                        run_id, RunState.TESTING, f"vertical:{current.plan_version}:test"
                    )
                elif role == AgentRole.REVIEWER and current.state == RunState.TESTING:
                    self.orchestrator.advance(
                        run_id, RunState.REVIEWING, f"vertical:{current.plan_version}:review"
                    )
                attempt = self._attempt(run_id, task)
                try:
                    if role == AgentRole.TESTER:
                        await self._validate(run_id, attempt, workspace.path, policy)
                    else:
                        schema = provider_output_schema(role)
                        with self.factory() as uow:
                            completed_review = (
                                next(
                                    (
                                        item
                                        for item in uow.execution.reviews(run_id)
                                        if item.actor_session_id
                                        == attempt.assigned_actor_session_id
                                        and item.plan_version == current.plan_version
                                    ),
                                    None,
                                )
                                if role == AgentRole.REVIEWER
                                else None
                            )
                        if completed_review:
                            if completed_review.tree_hash != workspace_digest(
                                workspace, self.reviews.git
                            ):
                                raise ConflictError("Workspace changed after the persisted review")
                            output = completed_review.result.model_dump(mode="json")
                        else:
                            output = await self.worker.execute(
                                run_id, attempt.id, provider_id, context, schema
                            )
                        if role == AgentRole.REVIEWER:
                            self.reviews.record(
                                run_id,
                                attempt.assigned_actor_session_id,
                                ReviewResult.model_validate(output),
                                str(attempt.id),
                            )
                        else:
                            result = WorkerResult.model_validate(output)
                            if not result.completed:
                                raise ConflictError("Worker reported incomplete implementation")
                            with self.factory() as uow:
                                locked_run(uow, run_id)
                                record_artifacts(uow, workspace, attempt, result)
                                uow.commit()
                    self.orchestrator.transition_task(
                        run_id, attempt.id, TaskStatus.SUCCEEDED, f"vertical:finish:{attempt.id}"
                    )
                except (OrqalisError, asyncio.CancelledError):
                    with self.factory() as uow:
                        interrupted = locked_run(uow, run_id)
                    if interrupted.state in {
                        RunState.CANCELLED,
                        RunState.FAILED,
                        RunState.COMPLETED,
                    }:
                        raise
                    self.orchestrator.transition_task(
                        run_id, attempt.id, TaskStatus.BLOCKED, f"vertical:blocked:{attempt.id}"
                    )
                    self.orchestrator.advance(
                        run_id, RunState.BLOCKED, f"vertical:blocked:{attempt.id}"
                    )
                    raise
                if role == AgentRole.DEVELOPER:
                    await self._context_wave(run_id, provider_id, context, policy)
        with self.factory() as uow:
            current = locked_run(uow, run_id)
            records = uow.execution.reviews(run_id)
            plan = uow.runtime.get_plan(run_id, current.plan_version)
            return ExecutionSummary(
                run_id=run_id,
                workspace=workspace.path,
                state=current.state,
                review=records[-1] if records else None,
                completed_tasks=sum(task.status == TaskStatus.SUCCEEDED for task in plan.tasks)
                if plan
                else 0,
            )

    async def _context_wave(
        self, run_id: UUID, provider_id: str, context: ContextPack, policy: ExecutionPolicy
    ) -> None:
        read_roles = {AgentRole.ARCHITECT, AgentRole.PLANNER, AgentRole.REPAIR}
        while True:
            with self.factory() as uow:
                run = locked_run(uow, run_id)
                plan = uow.runtime.get_plan(run_id, run.plan_version)
                if plan is None or run.state != RunState.EXECUTING:
                    return
                active = [
                    t
                    for t in plan.tasks
                    if t.preferred_role in read_roles and t.status == TaskStatus.RUNNING
                ]
                ready = [t for t in ready_tasks(plan) if t.preferred_role in read_roles]
                wave = (active + ready)[: policy.max_parallel_tasks]
            if not wave:
                return
            results = await asyncio.gather(
                *(self._context_task(run_id, task, provider_id, context) for task in wave),
                return_exceptions=True,
            )
            errors = [item for item in results if isinstance(item, BaseException)]
            if errors:
                if isinstance(errors[0], PolicyDeniedError):
                    raise errors[0]
                with self.factory() as uow:
                    current = locked_run(uow, run_id)
                    active_attempts = any(
                        a.status == TaskStatus.RUNNING for a in uow.runtime.executions(run_id)
                    )
                if current.state == RunState.EXECUTING and not active_attempts:
                    self.orchestrator.advance(
                        run_id, RunState.BLOCKED, f"context:blocked:{wave[0].id}"
                    )
                raise errors[0]

    async def _context_task(
        self,
        run_id: UUID,
        task: Task,
        provider_id: str,
        context: ContextPack,
    ) -> None:
        attempt = self._attempt(run_id, task)
        try:
            output = await self.worker.execute(
                run_id,
                attempt.id,
                provider_id,
                context,
                provider_output_schema(task.preferred_role),
            )
            if not WorkerResult.model_validate(output).completed:
                raise ConflictError("Context worker reported incomplete work")
            self.orchestrator.transition_task(
                run_id, attempt.id, TaskStatus.SUCCEEDED, f"context:finished:{attempt.id}"
            )
        except (OrqalisError, asyncio.CancelledError):
            with self.factory() as uow:
                run = locked_run(uow, run_id)
            if run.state == RunState.EXECUTING:
                self.orchestrator.transition_task(
                    run_id, attempt.id, TaskStatus.BLOCKED, f"context:blocked:{attempt.id}"
                )
            raise

    def _attempt(self, run_id: UUID, task: Task) -> TaskExecution:
        if task.status == TaskStatus.RUNNING:
            with self.factory() as uow:
                return next(
                    item
                    for item in uow.runtime.executions(run_id)
                    if item.task_id == task.id and item.status == TaskStatus.RUNNING
                )
        return self.orchestrator.start_task(
            run_id, task.id, f"vertical:start:{task.id}:attempt:{task.attempt_count + 1}"
        )

    async def _validate(
        self, run_id: UUID, attempt: TaskExecution, path: "Path", policy: ExecutionPolicy
    ) -> None:
        contract = self.goals.get(run_id)
        for criterion in contract.criteria:
            if criterion.validation_spec.kind in {"review", "manual"}:
                continue
            key = f"validation:{attempt.id}:{criterion.id}"
            await at_checkpoint(
                self.goals.validate,
                run_id,
                criterion.key,
                WorkspaceEvaluator(path, policy),
                key,
                attempt.id,
            )
