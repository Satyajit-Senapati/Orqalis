from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

from orqalis.agents.routing import CapabilityRouter
from orqalis.agents.service import AgentExecutionService
from orqalis.config.settings import Settings
from orqalis.core.approval_subjects import goal_subject
from orqalis.core.approvals import ApprovalService
from orqalis.core.delivery import DeliveryCoordinator
from orqalis.core.executor import RunExecutor
from orqalis.core.external import ExternalWorkService
from orqalis.core.goals import GoalService
from orqalis.core.orchestrator import Orchestrator
from orqalis.core.plan_preview import PlanPreviewService
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.projects import ProjectService
from orqalis.core.requirements import RequirementsCoordinator
from orqalis.core.runtime_support import emit, locked_run
from orqalis.core.vertical_plan import VerticalPlanner
from orqalis.delivery.inspection import ChangeInspectionService
from orqalis.domain.acceptance import GoalDraft
from orqalis.domain.approval import ApprovalStage, ApprovalStatus, ControlMode
from orqalis.domain.base import utc_now
from orqalis.domain.capabilities import SkillCatalogEntry
from orqalis.domain.errors import ConflictError, NotFoundError, PolicyDeniedError
from orqalis.domain.events import Event, EventPayload, EventType
from orqalis.domain.project import Project, ProjectSettings
from orqalis.domain.projections import RunSnapshot
from orqalis.domain.run import Run, RunState
from orqalis.execution.review import ReviewService
from orqalis.execution.tools import ToolService
from orqalis.execution.worker import AgentWorker
from orqalis.execution.workspaces import ExecutionWorkspaces
from orqalis.git.service import LocalGitService
from orqalis.memory.brain import ProjectBrainService
from orqalis.memory.service import MemoryService
from orqalis.observability.projections import SnapshotProjectionService
from orqalis.persistence.database import create_database_engine, session_factory
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork
from orqalis.providers.configuration import configured_providers
from orqalis.providers.ports import AgentProvider
from orqalis.security.redaction import safe_diagnostic
from orqalis.skills.registry import SkillRegistry
from orqalis.workspace.manager import WorktreeManager


class Orqalis:
    """Composition root and shared Python SDK for CLI, API and future MCP clients."""

    def __init__(
        self,
        settings: Settings | None = None,
        unit_of_work: Callable[[], ProjectUnitOfWork] | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.engine = create_database_engine(self.settings) if unit_of_work is None else None
        if unit_of_work is not None:
            self.unit_of_work = unit_of_work
        else:
            assert self.engine is not None
            sessions = session_factory(self.engine)
            self.unit_of_work = lambda: SQLProjectUnitOfWork(sessions)
        self.git = LocalGitService()
        self.projects = ProjectService(self.unit_of_work, self.git)
        self.memory = MemoryService(self.unit_of_work, self.git)
        self.brain = ProjectBrainService(self.unit_of_work, self.memory)
        self.changes = ChangeInspectionService(self.unit_of_work, self.git)
        self.goals = GoalService(self.unit_of_work)
        self.orchestrator = Orchestrator(self.unit_of_work)
        self.approvals = ApprovalService(self.unit_of_work)
        self.plans = PlanPreviewService(
            self.unit_of_work, self.orchestrator, self.goals, self.memory, self.git, self.approvals
        )
        self.projections = SnapshotProjectionService(self.unit_of_work)
        self.delivery = DeliveryCoordinator(
            self.unit_of_work, self.orchestrator, self.goals, self.git, self.approvals
        )

    def list_skills(self) -> tuple[SkillCatalogEntry, ...]:
        bundled = Path(__file__).parent / "skills" / "bundled"
        registry = SkillRegistry((bundled, *self.settings.skill_roots))
        if any(
            safe_diagnostic(metadata.model_dump_json()) != metadata.model_dump_json()
            for metadata in registry.discover()
        ):
            raise PolicyDeniedError("Skill catalog contains private or sensitive metadata")
        return tuple(
            SkillCatalogEntry(
                metadata=metadata,
                source="bundled" if directory.parent == bundled.resolve() else "configured",
            )
            for metadata, directory, _ in registry.entries.values()
        )

    def agent_service(
        self, providers: tuple[AgentProvider, ...] | None = None
    ) -> AgentExecutionService:
        roots = (Path(__file__).parent / "skills" / "bundled", *self.settings.skill_roots)
        registry = SkillRegistry(roots)
        router = CapabilityRouter(
            registry, providers if providers is not None else configured_providers(self.settings)
        )
        return AgentExecutionService(self.unit_of_work, router)

    def requirements(
        self, providers: tuple[AgentProvider, ...] | None = None
    ) -> RequirementsCoordinator:
        return RequirementsCoordinator(
            self.unit_of_work,
            self.orchestrator,
            self.goals,
            self.memory,
            self.agent_service(providers),
        )

    def executor(
        self, workspaces_root: Path, providers: tuple[AgentProvider, ...] | None = None
    ) -> RunExecutor:
        worker = AgentWorker(
            self.unit_of_work,
            self.agent_service(providers),
            ToolService(self.unit_of_work, self.git),
        )
        return RunExecutor(
            self.unit_of_work,
            self.orchestrator,
            self.goals,
            self.memory,
            ExecutionWorkspaces(self.unit_of_work, WorktreeManager(workspaces_root, self.git)),
            worker,
            ReviewService(self.unit_of_work, self.git),
            self.approvals,
            self.plans,
        )

    def external_work(self, workspaces_root: Path) -> ExternalWorkService:
        return ExternalWorkService(
            self.unit_of_work,
            self.orchestrator,
            self.goals,
            self.memory,
            ExecutionWorkspaces(self.unit_of_work, WorktreeManager(workspaces_root, self.git)),
            SkillRegistry(
                (Path(__file__).parent / "skills" / "bundled", *self.settings.skill_roots)
            ),
            self.git,
            self.approvals,
            self.plans,
        )

    def close(self) -> None:
        if self.engine:
            self.engine.dispose()

    def initialize(self, path: Path, project_settings: ProjectSettings | None = None) -> Project:
        project = self.projects.initialize(
            path,
            project_settings
            or ProjectSettings(max_repair_iterations=self.settings.max_repair_iterations),
        )
        self.memory.refresh(project)
        return project

    def list_projects(self) -> tuple[Project, ...]:
        with self.unit_of_work() as uow:
            return uow.projects.list()

    def get_project(self, project_id: UUID) -> Project:
        with self.unit_of_work() as uow:
            project = uow.projects.get(project_id)
            if project is None:
                raise NotFoundError("Project not found")
            return project

    def list_runs(self, project_id: UUID | None = None) -> tuple[Run, ...]:
        with self.unit_of_work() as uow:
            return uow.runs.list(project_id)

    def prepare_run(
        self,
        project_id: UUID,
        request: str,
        branch: str,
        goal: GoalDraft | None = None,
        mode: ControlMode = ControlMode.AUTONOMOUS,
        gates: frozenset[ApprovalStage] | None = None,
    ) -> RunSnapshot:
        if mode == ControlMode.AUTONOMOUS and gates:
            raise PolicyDeniedError("Custom approval gates require supervised mode")
        project = self.get_project(project_id)
        self.git.validate_branch(project.repo_root, branch, project.settings.protected_branches)
        status = self.git.status(project.repo_root)
        if goal is None:
            run = self.goals.create_pending(project, request, branch, status.head, mode, gates)
        else:
            run, _ = self.goals.create(project, request, branch, status.head, goal, mode, gates)
        return self.continue_preparation(run.id)

    def continue_preparation(self, run_id: UUID) -> RunSnapshot:
        """Resume context preparation with the same run identity and durable receipts."""
        with self.unit_of_work() as lease:
            if not lease.execution.try_run_lock(run_id):
                raise ConflictError("Another controller owns this run")
            with self.unit_of_work() as uow:
                run = locked_run(uow, run_id)
            if run.state == RunState.BLOCKED and run.resume_state == RunState.CONTEXT_SYNC:
                run = self.orchestrator.resume(run_id, f"prepare:resume:{uuid4()}")
            if run.state == RunState.RECEIVED:
                run = self.orchestrator.advance(run_id, RunState.CONTEXT_SYNC, "prepare:context")
            if run.state == RunState.CONTEXT_SYNC:
                self._synchronize_context(run)
                run = self.orchestrator.advance(run_id, RunState.ANALYZING, "prepare:analyzing")
            if run.state == RunState.ANALYZING and run.current_goal_version_id:
                # Provider requirements may have a pending actor completion checkpoint.
                with self.unit_of_work() as uow:
                    prepared = uow.runtime.tasks(run_id)
                if not prepared:
                    self.orchestrator.advance(run_id, RunState.GOAL_DEFINED, "prepare:goal")
            elif run.state not in {RunState.ANALYZING, RunState.GOAL_DEFINED}:
                raise ConflictError("Run is beyond context preparation or cannot be resumed")
            return self.snapshot(run_id)

    def _synchronize_context(self, run: Run) -> None:
        with self.unit_of_work() as uow:
            current = locked_run(uow, run.id)
            if uow.events.by_key(run.id, "prepare:context-pack"):
                return
            emit(
                uow,
                current,
                EventType.MEMORY_SYNC_STARTED,
                "prepare:memory-start",
                utc_now(),
                EventPayload(summary="Synchronizing committed project context"),
            )
            uow.commit()
        try:
            context = self.memory.context(self.get_project(run.project_id), run.request)
        except Exception:
            if self.snapshot(run.id).run.state == RunState.CONTEXT_SYNC:
                self.orchestrator.advance(
                    run.id, RunState.BLOCKED, f"prepare:context-blocked:{uuid4()}"
                )
            raise
        with self.unit_of_work() as uow:
            current = locked_run(uow, run.id)
            if current.state != RunState.CONTEXT_SYNC:
                raise ConflictError("Run changed during context preparation")
            emit(
                uow,
                current,
                EventType.MEMORY_SYNC_COMPLETED,
                "prepare:memory-end",
                utc_now(),
                EventPayload(summary="Committed context synchronized"),
            )
            emit(
                uow,
                current,
                EventType.CONTEXT_PACK_CREATED,
                "prepare:context-pack",
                utc_now(),
                EventPayload(memory_ids=tuple(match.item.id for match in context.items)),
            )
            uow.commit()

    def replan(self, run_id: UUID, key: str | None = None) -> Run:
        if key:
            with self.unit_of_work() as uow:
                current = locked_run(uow, run_id)
                prior = uow.events.by_key(run_id, f"replan:{key}")
                if prior and prior.payload.goal_version_id == current.current_goal_version_id:
                    return current
        contract = self.goals.get(run_id)
        requested = self.approvals.ensure(
            run_id,
            ApprovalStage.GOAL,
            contract.goal.version,
            goal_subject(contract),
            "Review revised goal and acceptance criteria before replanning",
        )
        if requested is not None and requested.status != ApprovalStatus.APPROVED:
            raise PolicyDeniedError(f"Goal approval required: {requested.id}")
        state = self.snapshot(run_id)
        project = self.get_project(state.run.project_id)
        plan = VerticalPlanner().plan(
            self.goals.get(run_id),
            self.memory.context(project, state.run.request),
            version=state.run.plan_version + 1,
        )
        return self.orchestrator.install_revised_goal_plan(plan, key or str(uuid4()))

    def snapshot(self, run_id: UUID) -> RunSnapshot:
        return self.projections.get_snapshot(run_id)

    def events(self, run_id: UUID, after: int = 0, limit: int | None = None) -> tuple[Event, ...]:
        with self.unit_of_work() as uow:
            locked_run(uow, run_id)
            return uow.events.list(run_id, after, limit)

    def cancel(self, run_id: UUID, key: str | None = None) -> Run:
        return self.orchestrator.advance(run_id, RunState.CANCELLED, key or str(uuid4()))

    def pause(self, run_id: UUID, key: str | None = None) -> Run:
        return self.orchestrator.advance(run_id, RunState.PAUSED, key or str(uuid4()))

    def resume(self, run_id: UUID, key: str | None = None) -> Run:
        return self.orchestrator.resume(run_id, key or str(uuid4()))
