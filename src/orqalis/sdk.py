from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

from orqalis.agents.routing import CapabilityRouter
from orqalis.agents.service import AgentExecutionService
from orqalis.bootstrap import ProjectBootstrapService
from orqalis.config.settings import Settings
from orqalis.context.builder import ProjectContextBuilder
from orqalis.context.models import ProjectContextPack
from orqalis.context.service import TaskContextService
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
from orqalis.domain.errors import ConflictError, InputError, NotFoundError, PolicyDeniedError
from orqalis.domain.events import Event, EventPayload, EventType
from orqalis.domain.project import Project, ProjectSettings
from orqalis.domain.projections import RunSnapshot
from orqalis.domain.run import Run, RunState
from orqalis.execution.review import ReviewService
from orqalis.execution.tools import ToolService
from orqalis.execution.worker import AgentWorker
from orqalis.execution.workspaces import ExecutionWorkspaces
from orqalis.git.service import GitError, LocalGitService
from orqalis.graph import ProjectGraph, ProjectGraphEngine
from orqalis.indexing import ProjectIndex, ProjectIndexBuildResult
from orqalis.memory.brain import ProjectBrainService
from orqalis.memory.curated import (
    CuratedMemoryStore,
    MemoryRecordStatus,
    MemoryRevalidationResult,
)
from orqalis.memory.service import MemoryService
from orqalis.observability.event_bus import ProjectEventBus
from orqalis.observability.projections import SnapshotProjectionService
from orqalis.persistence.filesystem import (
    FilesystemProjectUnitOfWork,
    ProjectLayout,
    TaskCapsuleStore,
    resolve_project_root,
)
from orqalis.providers.configuration import configured_providers
from orqalis.providers.ports import AgentProvider
from orqalis.security.redaction import safe_diagnostic
from orqalis.skills.registry import SkillRegistry
from orqalis.tasks.history import TaskHistoryService
from orqalis.workspace.manager import WorktreeManager


class Orqalis:
    """Composition root and shared Python SDK for CLI, API and future MCP clients."""

    def __init__(
        self,
        settings: Settings | None = None,
        unit_of_work: Callable[[], ProjectUnitOfWork] | None = None,
        root: Path | None = None,
        event_bus: ProjectEventBus | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.event_bus = event_bus or ProjectEventBus()
        self.project_root: Path | None = None
        self._task_store: TaskCapsuleStore | None = None
        self._contexts: TaskContextService | None = None
        self._task_history: TaskHistoryService | None = None
        self.unit_of_work: Callable[[], ProjectUnitOfWork]
        if unit_of_work is not None:
            self.unit_of_work = unit_of_work
        else:
            selected_root = root if root is not None else self.settings.project_root
            self.project_root = resolve_project_root(selected_root)
            store = TaskCapsuleStore.from_root(self.project_root)
            self._task_store = store
            self.unit_of_work = lambda: FilesystemProjectUnitOfWork(store, self.event_bus)
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
        """Release composition-owned resources.

        Filesystem units of work are scoped to each operation and close themselves.
        The method remains part of the SDK lifecycle for injected adapters and callers.
        """

    @property
    def contexts(self) -> TaskContextService | None:
        """Return project context services once the bound store is initialized."""

        if (
            self._contexts is None
            and self.project_root is not None
            and self._task_store is not None
            and ProjectLayout(self.project_root).manifest.is_file()
        ):
            self._contexts = TaskContextService(self.project_root, store=self._task_store)
        return self._contexts

    @property
    def task_history(self) -> TaskHistoryService | None:
        """Return validated Task Capsule history for an initialized local project."""

        if (
            self._task_history is None
            and self.project_root is not None
            and ProjectLayout(self.project_root).manifest.is_file()
        ):
            self._task_history = TaskHistoryService(self.project_root)
        return self._task_history

    def project_context(self, task: str, max_chars: int | None = None) -> ProjectContextPack:
        if self.contexts is None or self.project_root is None:
            raise NotFoundError("Project is not initialized; run orqalis init")
        return ProjectContextBuilder(self.project_root, git=self.git).build(task, max_chars)

    def rebuild_project_index(self) -> ProjectIndexBuildResult:
        if self.project_root is None:
            raise PolicyDeniedError("Project index requires a root-bound filesystem SDK")
        return ProjectIndex(self.project_root, git=self.git).rebuild()

    def project_graph(self) -> ProjectGraph:
        if self.project_root is None:
            raise PolicyDeniedError("Project graph requires a root-bound filesystem SDK")
        return ProjectGraphEngine(self.project_root, git=self.git).refresh().graph

    def search_project_memory(self, query: str, limit: int = 10) -> tuple[MemoryRecordStatus, ...]:
        """Search curated durable memory and report current provenance freshness."""

        if len(query) > 10_000 or not 1 <= limit <= 100:
            raise InputError("Memory search requires a limit of 1..100 and query up to 10000 chars")
        if self.project_root is None:
            raise PolicyDeniedError("Project memory requires a root-bound filesystem SDK")
        store = CuratedMemoryStore(ProjectLayout(self.project_root))
        try:
            head = self.git.status(self.project_root).head
        except GitError:
            head = None
        return tuple(store.status(record, head) for record in store.search(query, limit))

    def project_memory_status(self) -> tuple[MemoryRecordStatus, ...]:
        """Return freshness for every approved durable memory record."""

        if self.project_root is None:
            raise PolicyDeniedError("Project memory requires a root-bound filesystem SDK")
        head = self.git.status(self.project_root).head
        store = CuratedMemoryStore(ProjectLayout(self.project_root))
        return tuple(store.status(record, head) for record in store.list())

    def revalidate_project_memory(
        self, record_ids: tuple[str, ...] = ()
    ) -> MemoryRevalidationResult:
        """Explicitly revalidate selected stale memory provenance at the current HEAD."""

        if self.project_root is None:
            raise PolicyDeniedError("Project memory requires a root-bound filesystem SDK")
        head = self.git.status(self.project_root).head
        return CuratedMemoryStore(ProjectLayout(self.project_root)).revalidate(head, record_ids)

    def initialize(self, path: Path, project_settings: ProjectSettings | None = None) -> Project:
        if self.project_root is not None and resolve_project_root(path) != self.project_root:
            raise PolicyDeniedError("Initialization path does not match the bound project root")
        project = self.projects.initialize(
            path,
            project_settings
            or ProjectSettings(max_repair_iterations=self.settings.max_repair_iterations),
        )
        ProjectBootstrapService(project.repo_root, git=self.git).bootstrap(project)
        # Maintain the deletable legacy search projection for API compatibility. Agent
        # context, curated memory, graph and task history use their authoritative stores.
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
            if self.contexts is not None:
                self.contexts.create(run.id)
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
