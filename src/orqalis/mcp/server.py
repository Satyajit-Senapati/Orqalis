from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from orqalis import __version__
from orqalis.agents.roles import role_definition
from orqalis.context.builder import ProjectContextBuilder
from orqalis.context.models import ProjectContextPack
from orqalis.domain.acceptance import GoalContract, GoalDraft
from orqalis.domain.agent import AgentRole
from orqalis.domain.artifact import Finding
from orqalis.domain.base import Contract
from orqalis.domain.capabilities import LoadedSkill, RoleDefinition, SkillMetadata
from orqalis.domain.delivery import DeliveryResult
from orqalis.domain.errors import ConflictError, OrqalisError, PolicyDeniedError
from orqalis.domain.execution import ExecutionSummary, WorkerResult
from orqalis.domain.external import FindingReport, WorkAssignment
from orqalis.domain.memory import ArchitectureEntity, ArchitectureRelation
from orqalis.domain.plan import TaskPlan
from orqalis.domain.project import Project
from orqalis.domain.projections import RunSnapshot
from orqalis.domain.provider import ProviderDescriptor
from orqalis.domain.task import TaskExecution, TaskStatus
from orqalis.graph import GraphNode, GraphNodeKind, ProjectGraph, ProjectGraphEngine
from orqalis.mcp.policy import MCPPolicy
from orqalis.memory.curated import (
    CuratedMemoryStore,
    MemoryCategory,
    MemoryProposal,
    MemoryProvenance,
    MemoryRecordStatus,
    MemoryRevalidationResult,
    source_hashes,
)
from orqalis.persistence.filesystem import ProjectLayout, resolve_project_root
from orqalis.providers.configuration import configured_providers
from orqalis.providers.ports import AgentProvider
from orqalis.sdk import Orqalis
from orqalis.security.redaction import safe_diagnostic
from orqalis.skills.registry import SkillRegistry
from orqalis.tasks.history import TaskCapsuleView, TaskHistoryEntry, TaskHistoryService


class Capabilities(Contract):
    agents: tuple[RoleDefinition, ...]
    skills: tuple[SkillMetadata, ...]
    providers: tuple[ProviderDescriptor, ...]


class ArchitectureGraph(Contract):
    entities: tuple[ArchitectureEntity, ...]
    relations: tuple[ArchitectureRelation, ...]


@contextmanager
def boundary() -> Iterator[None]:
    try:
        yield
    except OrqalisError as exc:
        raise ToolError(f"{exc.code}: {safe_diagnostic(str(exc))}") from None
    except Exception:
        # SDK/provider exceptions may contain credentials and raw input.
        raise ToolError(
            "internal_error: operation failed; inspect Orqalis runtime status"
        ) from None


def create_mcp(
    sdk: Orqalis, policy: MCPPolicy, providers: tuple[AgentProvider, ...] | None = None
) -> MCPServer[None]:
    server: MCPServer[None] = MCPServer(
        "Orqalis",
        version=__version__,
        log_level="WARNING",
        instructions=(
            "Retrieve project context before repository inspection. Work only in the assigned "
            "worktree. Report structured results; Orqalis independently tests and reviews "
            "acceptance. Never report hidden reasoning or credentials."
        ),
    )
    registry = SkillRegistry(
        (Path(__file__).parents[1] / "skills" / "bundled", *sdk.settings.skill_roots)
    )
    external = sdk.external_work(policy.workspaces_root)
    reads = ToolAnnotations(read_only_hint=True, open_world_hint=False)
    writes = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)

    def scoped_run(run_id: UUID) -> RunSnapshot:
        snapshot = sdk.snapshot(run_id)
        if snapshot.run.project_id != policy.project_id:
            raise PolicyDeniedError("Run is outside this server's authorized project")
        return snapshot

    def scoped_root() -> Path:
        project = sdk.get_project(policy.project_id)
        root = resolve_project_root(sdk.project_root or project.repo_root)
        if root != project.repo_root.resolve(strict=True):
            raise PolicyDeniedError("SDK root does not match the authorized MCP project")
        return root

    @server.tool(annotations=reads)
    def get_project() -> Project:
        """Get this server's authorized project and repository policy."""
        with boundary():
            return sdk.get_project(policy.project_id)

    @server.tool(annotations=reads)
    def get_project_context(task: str, max_chars: int = 20000) -> ProjectContextPack:
        """Retrieve selective graph, curated memory, task history, and Git context."""
        with boundary():
            return ProjectContextBuilder(scoped_root()).build(task, max_chars)

    @server.tool(annotations=reads)
    def search_project_memory(query: str, limit: int = 10) -> tuple[MemoryRecordStatus, ...]:
        """Search curated durable project memory with provenance freshness."""
        with boundary():
            scoped_root()
            return sdk.search_project_memory(query, limit)

    @server.tool(annotations=reads)
    def get_architecture() -> ArchitectureGraph:
        """Read the persisted architecture graph after Git freshness validation."""
        with boundary():
            project = sdk.get_project(policy.project_id)
            entities, relations = sdk.memory.graph(project)
            return ArchitectureGraph(entities=entities, relations=relations)

    @server.tool(annotations=reads)
    def get_decisions(topic: str = "") -> tuple[MemoryRecordStatus, ...]:
        """Retrieve curated ADR/decision knowledge."""
        with boundary():
            return tuple(
                item
                for item in sdk.search_project_memory(topic, 100)
                if item.record.category == MemoryCategory.DECISION
            )

    @server.tool(annotations=reads)
    def get_related_files(task: str) -> tuple[str, ...]:
        """Retrieve source paths selected by the same Git-aware Context Pack service."""
        with boundary():
            return get_project_context(task).relevant_files

    @server.tool(annotations=reads)
    def get_project_graph() -> ProjectGraph:
        """Read the typed deterministic repository graph for this project."""
        with boundary():
            return ProjectGraphEngine(scoped_root()).refresh().graph

    @server.tool(annotations=reads)
    def get_related_symbols(task: str, limit: int = 20) -> tuple[GraphNode, ...]:
        """Return the highest-ranked non-file symbols for a task query."""
        with boundary():
            if not 1 <= limit <= 100:
                raise PolicyDeniedError("Symbol limit must be between 1 and 100")
            pack = get_project_context(task)
            return tuple(item.node for item in pack.graph if item.node.kind != GraphNodeKind.FILE)[
                :limit
            ]

    @server.tool(annotations=reads)
    def list_tasks(limit: int = 100) -> tuple[TaskHistoryEntry, ...]:
        """List compact project-local Task Capsule history."""
        with boundary():
            return TaskHistoryService(scoped_root()).list(limit)

    @server.tool(annotations=reads)
    def get_task(task_id: str) -> TaskCapsuleView:
        """Read one validated Task Capsule without exposing raw filesystem access."""
        with boundary():
            return TaskHistoryService(scoped_root()).get(task_id)

    @server.tool(annotations=reads)
    def get_task_context(task_id: str) -> ProjectContextPack | None:
        """Read the selective Context Pack persisted for one Task Capsule."""
        with boundary():
            return TaskHistoryService(scoped_root()).get(task_id).context

    @server.tool(annotations=writes)
    def propose_memory_update(
        category: MemoryCategory,
        title: str,
        content: str,
        rationale: str,
        source_paths: tuple[str, ...] = (),
        evidence: tuple[str, ...] = (),
        introduced_by_task: str | None = None,
        confidence: float = 1.0,
    ) -> MemoryProposal:
        """Stage a secret-scanned durable memory proposal for review."""
        with boundary():
            policy.require_work()
            root = scoped_root()
            if introduced_by_task is not None:
                TaskHistoryService(root).get(introduced_by_task)
            project = sdk.get_project(policy.project_id)
            head = sdk.git.status(project.repo_root).head
            store = CuratedMemoryStore(ProjectLayout(root))
            record = store.new_record(
                category,
                title,
                content,
                MemoryProvenance(
                    type="repository" if source_paths else "user",
                    paths=source_paths,
                    content_hashes=source_hashes(root, source_paths),
                ),
                verified_commit=head,
                introduced_by_task=introduced_by_task,
                confidence=confidence,
            )
            return store.propose(
                record,
                rationale,
                policy=store.configured_policy(),
                evidence=evidence,
            )

    @server.tool(annotations=writes)
    def refresh_project_memory(
        record_ids: tuple[str, ...] = (),
    ) -> MemoryRevalidationResult:
        """Explicitly revalidate selected stale curated-memory provenance."""
        with boundary():
            policy.require_work()
            scoped_root()
            return sdk.revalidate_project_memory(record_ids)

    @server.tool(annotations=writes)
    def start_task(request: str, branch: str, goal: GoalDraft) -> RunSnapshot:
        """Create a run with an explicit goal/acceptance contract; does not execute commands."""
        with boundary():
            policy.require_work()
            return sdk.prepare_run(
                policy.project_id,
                request,
                branch,
                goal,
                policy.control_mode,
                policy.approval_gates,
            )

    @server.tool(annotations=reads)
    def get_run(run_id: UUID) -> RunSnapshot:
        """Inspect the authoritative run, actors, timing and evidence projection."""
        with boundary():
            return scoped_run(run_id)

    @server.tool(annotations=reads)
    def get_goal(run_id: UUID) -> GoalContract:
        """Read the immutable current acceptance contract."""
        with boundary():
            scoped_run(run_id)
            return sdk.goals.get(run_id)

    @server.tool(annotations=reads)
    def get_plan(run_id: UUID) -> TaskPlan | None:
        """Read current DAG membership and preserved task history."""
        with boundary():
            snapshot = scoped_run(run_id)
            with sdk.unit_of_work() as uow:
                return uow.runtime.get_plan(run_id, snapshot.run.plan_version)

    @server.tool(annotations=writes)
    def get_next_work(
        run_id: UUID, worker_capabilities: tuple[str, ...] = ()
    ) -> WorkAssignment | None:
        """Claim dependency-ready external implementation; returns an owned workspace."""
        with boundary():
            execution = policy.require_work()
            scoped_run(run_id)
            return external.next_work(run_id, execution, worker_capabilities)

    @server.tool(annotations=writes)
    def report_result(run_id: UUID, execution_id: UUID, result: WorkerResult) -> TaskExecution:
        """Record an assigned implementation result; this cannot pass acceptance."""
        with boundary():
            policy.require_work()
            scoped_run(run_id)
            return external.report(run_id, execution_id, result)

    @server.tool(annotations=writes)
    def report_finding(
        run_id: UUID,
        execution_id: UUID,
        finding: FindingReport,
        idempotency_key: str,
    ) -> Finding:
        """Report a source-backed issue; only independent review can resolve blockers."""
        with boundary():
            policy.require_work()
            scoped_run(run_id)
            return external.report_finding(run_id, execution_id, finding, idempotency_key)

    @server.tool(annotations=writes)
    async def review_run(run_id: UUID) -> ExecutionSummary:
        """Run approved validators and an independent reviewer; return targeted repairs."""
        with boundary():
            execution = policy.require_work()
            snapshot = scoped_run(run_id)
            with sdk.unit_of_work() as uow:
                plan = uow.runtime.get_plan(run_id, snapshot.run.plan_version)
                if plan is None or any(
                    t.preferred_role in {AgentRole.DEVELOPER, AgentRole.REPAIR}
                    and t.status != TaskStatus.SUCCEEDED
                    for t in plan.tasks
                ):
                    raise ConflictError(
                        "Report all assigned implementation before requesting review"
                    )
            return await sdk.executor(policy.workspaces_root, providers).execute(
                run_id, policy.reviewer_provider, execution, repair_automatically=False
            )

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=True,
            open_world_hint=True,
        )
    )
    async def finalize_run(run_id: UUID) -> DeliveryResult:
        """Request gated delivery using only the server-approved immutable delivery policy."""
        with boundary():
            delivery = policy.require_delivery()
            scoped_run(run_id)
            return await sdk.delivery.finalize(run_id, delivery)

    @server.tool(annotations=reads)
    def list_capabilities() -> Capabilities:
        """List role, skill and configured provider metadata."""
        with boundary():
            available = providers if providers is not None else configured_providers(sdk.settings)
            for skill in registry.discover():
                if safe_diagnostic(skill.model_dump_json()) != skill.model_dump_json():
                    raise PolicyDeniedError("Skill metadata contains private or sensitive content")
            return Capabilities(
                agents=tuple(role_definition(role) for role in AgentRole),
                skills=registry.discover(),
                providers=tuple(p.descriptor for p in available),
            )

    @server.tool(annotations=reads)
    def list_agents() -> tuple[RoleDefinition, ...]:
        """List specialized role definitions and permission profiles."""
        return list_capabilities().agents

    @server.tool(annotations=reads)
    def list_skills(query: str = "") -> tuple[SkillMetadata, ...]:
        """Discover skill metadata without loading instructions."""
        return tuple(
            skill
            for skill in list_capabilities().skills
            if not query or query.casefold() in skill.model_dump_json().casefold()
        )

    @server.tool(annotations=reads)
    def get_skill(skill_id: str, version: str) -> LoadedSkill:
        """Load a discovered, explicitly versioned skill from trusted server roots."""
        with boundary():
            metadata = next(
                (s for s in registry.discover() if s.id == skill_id and s.version == version), None
            )
            if metadata is None:
                raise ConflictError("Skill version is not registered")
            return registry.load(metadata)

    @server.resource("orqalis://project")
    def project_resource() -> str:
        return get_project().model_dump_json()

    @server.resource("orqalis://runs/{run_id}")
    def run_resource(run_id: UUID) -> str:
        return get_run(run_id).model_dump_json()

    @server.resource("orqalis://architecture")
    def architecture_resource() -> str:
        return get_architecture().model_dump_json()

    @server.resource("orqalis://decisions")
    def decisions_resource() -> str:
        from pydantic import TypeAdapter

        return TypeAdapter(tuple[MemoryRecordStatus, ...]).dump_json(get_decisions()).decode()

    return server
