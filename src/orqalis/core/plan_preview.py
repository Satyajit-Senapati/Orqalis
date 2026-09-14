from collections.abc import Callable
from uuid import UUID

from orqalis.core.approval_subjects import goal_subject, plan_subject
from orqalis.core.approvals import ApprovalService
from orqalis.core.goals import GoalService
from orqalis.core.orchestrator import Orchestrator
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import locked_run, require_key
from orqalis.core.vertical_plan import VerticalPlanner
from orqalis.domain.approval import ApprovalStage, ApprovalStatus
from orqalis.domain.errors import ConflictError, NotFoundError, PolicyDeniedError
from orqalis.domain.memory import ContextPack, MemoryHealth
from orqalis.domain.plan import TaskPlan
from orqalis.domain.project import Project
from orqalis.domain.run import Run, RunState
from orqalis.git.contracts import GitService
from orqalis.memory.service import MemoryService


class PlanPreviewService:
    """Create a durable initial plan before any execution workspace is allocated."""

    def __init__(
        self,
        factory: Callable[[], ProjectUnitOfWork],
        orchestrator: Orchestrator,
        goals: GoalService,
        memory: MemoryService,
        git: GitService,
        approvals: ApprovalService | None = None,
    ) -> None:
        self.factory = factory
        self.orchestrator = orchestrator
        self.goals = goals
        self.memory = memory
        self.git = git
        self.approvals = approvals

    def preview(self, run_id: UUID, key: str) -> TaskPlan:
        """Persist version one and stop at PLANNED for operator inspection.

        A retry after a committed plan but interrupted state transition completes that
        transition using the stored plan. It never creates another plan version.
        """
        require_key(key)
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            already_planned = run.state == RunState.PLANNED and run.plan_version > 0
            if already_planned:
                plan = uow.runtime.get_plan(run_id, run.plan_version)
                if plan is None:
                    raise ConflictError("Current plan is missing")
            else:
                if run.state != RunState.GOAL_DEFINED:
                    raise ConflictError("Initial plan preview requires GOAL_DEFINED")
                if run.plan_version:
                    stored = uow.runtime.get_plan(run_id, run.plan_version)
                    if (
                        stored is None
                        or stored.version != 1
                        or stored.goal_version_id != run.current_goal_version_id
                    ):
                        raise ConflictError("Installed plan does not match the current goal")
                    plan = stored
                else:
                    project = uow.projects.get(run.project_id)
                    if project is None:
                        raise NotFoundError("Project not found")
                    plan = None

        if already_planned:
            assert plan is not None
            self._request_plan(run_id, plan)
            return plan

        if self.approvals is not None:
            contract = self.goals.get(run_id)
            approval = self.approvals.ensure(
                run_id,
                ApprovalStage.GOAL,
                contract.goal.version,
                goal_subject(contract),
                "Approve goal before planning",
            )
            if approval is not None and approval.status != ApprovalStatus.APPROVED:
                raise PolicyDeniedError(f"Goal approval required: {approval.id}")
        if plan is None:
            if project is None:
                raise NotFoundError("Project not found")
            # Runs execute their pinned base even if the source branch advances.
            # A moved HEAD cannot be used to refresh memory for this preview.
            # Read the base commit's tracked file map without allocating an
            # execution workspace; the worker refreshes memory in its worktree.
            if self.git.resolve_commit(project.repo_root, "HEAD") == run.base_commit:
                context = self.memory.context(project, run.request)
                if context.freshness.indexed_commit != run.base_commit:
                    context = self._base_context(run, project)
            else:
                context = self._base_context(run, project)
            plan = VerticalPlanner().plan(self.goals.get(run_id), context)
            self.orchestrator.install_plan(plan, key)
        self.orchestrator.advance(run_id, RunState.PLANNED, f"{key}:planned")
        with self.factory() as uow:
            current = locked_run(uow, run_id)
            persisted = uow.runtime.get_plan(run_id, current.plan_version)
            if persisted is None:
                raise ConflictError("Current plan is missing")
        self._request_plan(run_id, persisted)
        return persisted

    def _base_context(self, run: Run, project: Project) -> ContextPack:
        files = self.git.tracked_files(project.repo_root, run.base_commit)
        return ContextPack(
            project_id=project.id,
            task=run.request,
            items=(),
            relevant_files=files,
            freshness=MemoryHealth(
                project_id=project.id,
                indexed_commit=None,
                current_commit=run.base_commit,
                fresh=False,
                dirty_paths=(),
                active_items=0,
            ),
            confidence=0,
            targeted_inspection_paths=files,
            requires_inspection=True,
            size_chars=0,
        )

    def _request_plan(self, run_id: UUID, plan: TaskPlan) -> None:
        if self.approvals is not None:
            self.approvals.ensure(
                run_id,
                ApprovalStage.PLAN,
                plan.version,
                plan_subject(plan),
                "Review the dependency plan before execution",
            )

    def replace(self, plan: TaskPlan, expected_version: int, key: str) -> TaskPlan:
        """Replace an unexecuted preview using an operator-supplied typed DAG."""
        self.orchestrator.replace_preview_plan(plan, expected_version, key)
        with self.factory() as uow:
            persisted = uow.runtime.get_plan(plan.run_id, plan.version)
            if persisted is None:
                raise ConflictError("Replacement plan is missing")
        self._request_plan(plan.run_id, persisted)
        return persisted
