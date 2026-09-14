import hashlib
from collections.abc import Callable
from uuid import UUID, uuid5

from orqalis.agents.roles import effective_tools, role_definition
from orqalis.core.approval_subjects import goal_subject, plan_subject
from orqalis.core.approvals import ApprovalService
from orqalis.core.goals import GoalService
from orqalis.core.orchestrator import Orchestrator
from orqalis.core.plan_preview import PlanPreviewService
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit, locked_run, require_key
from orqalis.core.scheduler import ready_tasks
from orqalis.core.vertical_plan import VerticalPlanner
from orqalis.domain.agent import AgentRole
from orqalis.domain.approval import ApprovalStage, ApprovalStatus
from orqalis.domain.artifact import Finding
from orqalis.domain.base import utc_now
from orqalis.domain.capabilities import ToolName
from orqalis.domain.errors import ConflictError, NotFoundError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.execution import ExecutionPolicy, WorkerResult
from orqalis.domain.external import FindingReport, WorkAssignment
from orqalis.domain.run import RunState
from orqalis.domain.task import TaskExecution, TaskStatus
from orqalis.execution.artifacts import record_artifacts
from orqalis.execution.filesystem import ScopedFilesystem
from orqalis.execution.review import workspace_digest
from orqalis.execution.workspaces import ExecutionWorkspaces
from orqalis.git.service import LocalGitService
from orqalis.memory.service import MemoryService
from orqalis.security.redaction import safe_diagnostic
from orqalis.skills.registry import SkillRegistry


class ExternalWorkService:
    """Assistant-native implementation reports; acceptance remains independently reviewed."""

    def __init__(
        self,
        factory: Callable[[], ProjectUnitOfWork],
        orchestrator: Orchestrator,
        goals: GoalService,
        memory: MemoryService,
        workspaces: ExecutionWorkspaces,
        registry: SkillRegistry,
        git: LocalGitService,
        approvals: ApprovalService | None = None,
        plans: PlanPreviewService | None = None,
    ) -> None:
        self.factory, self.orchestrator, self.goals = factory, orchestrator, goals
        self.memory, self.workspaces, self.registry, self.git = memory, workspaces, registry, git
        self.approvals = approvals or ApprovalService(factory)
        self.plans = plans

    def next_work(
        self,
        run_id: UUID,
        policy: ExecutionPolicy,
        capabilities: tuple[str, ...] = (),
    ) -> WorkAssignment | None:
        with self.factory() as lease:
            if not lease.execution.try_run_lock(run_id):
                raise ConflictError("Another controller owns this run")
            return self._next(run_id, policy, capabilities)

    def _next(
        self, run_id: UUID, policy: ExecutionPolicy, capabilities: tuple[str, ...]
    ) -> WorkAssignment | None:
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            project = uow.projects.get(run.project_id)
            if project is None:
                raise NotFoundError("Project missing")
            if run.state not in {RunState.GOAL_DEFINED, RunState.PLANNED, RunState.EXECUTING}:
                return None
            allowed = effective_tools(AgentRole.DEVELOPER, project.settings.permissions)
            if ToolName.FILE_WRITE not in allowed:
                raise PolicyDeniedError("Project policy forbids implementation work")
            if (
                project.settings.allowed_providers
                and "external" not in project.settings.allowed_providers
            ):
                raise PolicyDeniedError("Project policy forbids external assistants")
        if run.state == RunState.GOAL_DEFINED:
            if self.plans is not None:
                self.plans.preview(run_id, "external")
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
                original_context = self.memory.context(project, run.request)
                self.orchestrator.install_plan(
                    VerticalPlanner().plan(contract, original_context), "external:plan"
                )
                self.orchestrator.advance(run_id, RunState.PLANNED, "external:planned")
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            plan = uow.runtime.get_plan(run_id, run.plan_version)
            if plan is None:
                raise NotFoundError("Current plan missing")
        requested = self.approvals.ensure(
            run_id,
            ApprovalStage.PLAN,
            run.plan_version,
            plan_subject(plan),
            "Review the dependency plan before external work",
        )
        if requested is not None and requested.status != ApprovalStatus.APPROVED:
            raise PolicyDeniedError(f"Plan approval required: {requested.id}")
        workspace = self.workspaces.ensure(run_id, policy)
        contract = self.goals.get(run_id)
        context = self.memory.context(
            project.model_copy(update={"repo_root": workspace.path}), run.request
        )
        if run.state == RunState.PLANNED:
            self.orchestrator.advance(
                run_id, RunState.EXECUTING, f"external:{run.plan_version}:executing"
            )
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            plan = uow.runtime.get_plan(run_id, run.plan_version)
            assert plan is not None
            attempts = uow.runtime.executions(run_id)
            active = [t for t in plan.tasks if t.status == TaskStatus.RUNNING]
            candidates = active or list(ready_tasks(plan))
            task = next(
                (
                    t
                    for t in candidates
                    if t.preferred_role
                    in {
                        AgentRole.DEVELOPER,
                        AgentRole.REPAIR,
                    }
                    and (not capabilities or set(t.required_capabilities) <= set(capabilities))
                ),
                None,
            )
            if task is None:
                return None
            attempt = next(
                (a for a in attempts if a.task_id == task.id and a.status == TaskStatus.RUNNING),
                None,
            )
            if attempt and not uow.events.by_key(run_id, f"external:assigned:{attempt.id}"):
                raise ConflictError("A provider worker owns this task")
        tools = effective_tools(task.preferred_role, project.settings.permissions)
        skills = self.registry.select(
            task.required_capabilities,
            tools,
            tags=tuple(
                dict.fromkeys(
                    (*project.settings.repository_profile.languages, *task.required_capabilities)
                )
            ),
            built_in=role_definition(task.preferred_role).capabilities,
            pins=project.settings.skill_pins,
        )
        attempt = attempt or self.orchestrator.start_task(
            run_id, task.id, f"external:start:{task.id}:attempt:{task.attempt_count + 1}"
        )
        refs = tuple(f"{s.metadata.id}@{s.metadata.version}:{s.content_hash}" for s in skills)
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            actor = next(
                a for a in uow.runtime.actors(run_id) if a.id == attempt.assigned_actor_session_id
            )
            uow.runtime.save_actor(
                actor.model_copy(
                    update={
                        "provider": "external",
                        "loaded_skills": refs,
                        "allowed_tools": tuple(str(tool) for tool in tools),
                    }
                )
            )
            emit(
                uow,
                run,
                EventType.AGENT_ASSIGNED,
                f"external:assigned:{attempt.id}",
                utc_now(),
                EventPayload(summary="Assistant-native implementation", skill_refs=refs),
                actor.id,
                task.id,
                attempt.id,
            )
            for ref in refs:
                emit(
                    uow,
                    run,
                    EventType.SKILL_LOADED,
                    f"external:skill:{attempt.id}:{ref}",
                    utc_now(),
                    EventPayload(skill_refs=(ref,)),
                    actor.id,
                    task.id,
                    attempt.id,
                )
            uow.commit()
        return WorkAssignment(
            task=task,
            execution=attempt,
            workspace=workspace.path,
            goal=contract,
            context=context,
            skills=skills,
            allowed_tools=tools,
        )

    def report(self, run_id: UUID, execution_id: UUID, result: WorkerResult) -> TaskExecution:
        with self.factory() as lease:
            if not lease.execution.try_run_lock(run_id):
                raise ConflictError("Another controller owns this run")
            with self.factory() as uow:
                run = locked_run(uow, run_id)
                if safe_diagnostic(result.model_dump_json()) != result.model_dump_json():
                    raise PolicyDeniedError("Unsafe external result")
                attempt = next(
                    (a for a in uow.runtime.executions(run_id) if a.id == execution_id), None
                )
                if not attempt or not uow.events.by_key(
                    run_id, f"external:assigned:{execution_id}"
                ):
                    raise PolicyDeniedError(
                        "Only externally assigned implementation may be reported"
                    )
                fingerprint = hashlib.sha256(result.model_dump_json().encode()).hexdigest()
                replay = uow.events.by_key(run_id, f"external:result:{execution_id}")
                if replay and replay.payload.reason != fingerprint:
                    raise ConflictError("External result differs from its persisted receipt")
                if not replay:
                    if run.state != RunState.EXECUTING or attempt.status != TaskStatus.RUNNING:
                        raise ConflictError("External task is not active")
                    if not result.completed:
                        raise ConflictError(
                            "Implementation is incomplete; continue the assigned task"
                        )
                    workspace = uow.execution.workspace(run_id)
                    if not workspace:
                        raise NotFoundError("Workspace missing")
                    digest = workspace_digest(workspace, self.git)
                    record_artifacts(uow, workspace, attempt, result)
                    emit(
                        uow,
                        run,
                        EventType.EXTERNAL_RESULT_REPORTED,
                        f"external:result:{execution_id}",
                        utc_now(),
                        EventPayload(summary=result.summary, reason=fingerprint, status=digest),
                        attempt.assigned_actor_session_id,
                        attempt.task_id,
                        attempt.id,
                    )
                    uow.commit()
            return self.orchestrator.transition_task(
                run_id, execution_id, TaskStatus.SUCCEEDED, f"external:finished:{execution_id}"
            )

    def report_finding(
        self,
        run_id: UUID,
        execution_id: UUID,
        report: FindingReport,
        key: str,
    ) -> Finding:
        require_key(key)
        encoded = report.model_dump_json()
        if safe_diagnostic(encoded) != encoded or safe_diagnostic(key) != key:
            raise PolicyDeniedError("Unsafe external finding")
        fingerprint = hashlib.sha256(f"{execution_id}:{encoded}".encode()).hexdigest()
        receipt_key = f"external:finding:{hashlib.sha256(key.encode()).hexdigest()}"
        finding_id = uuid5(run_id, receipt_key)
        with self.factory() as lease:
            if not lease.execution.try_run_lock(run_id):
                raise ConflictError("Another controller owns this run")
            with self.factory() as uow:
                run = locked_run(uow, run_id)
                attempt = next(
                    (a for a in uow.runtime.executions(run_id) if a.id == execution_id), None
                )
                if not attempt or not uow.events.by_key(
                    run_id, f"external:assigned:{execution_id}"
                ):
                    raise PolicyDeniedError("Only externally assigned work may report findings")
                replay = uow.events.by_key(run_id, receipt_key)
                if replay:
                    if replay.payload.reason != fingerprint:
                        raise ConflictError("Finding key belongs to a different report")
                    return next(f for f in uow.delivery.findings(run_id) if f.id == finding_id)
                if run.state != RunState.EXECUTING or attempt.status != TaskStatus.RUNNING:
                    raise ConflictError("External task is not active")
                goal = (
                    uow.runs.get_goal(run.current_goal_version_id)
                    if run.current_goal_version_id
                    else None
                )
                if report.criterion_id and (
                    not goal or report.criterion_id not in {c.id for c in goal.criteria}
                ):
                    raise PolicyDeniedError("Finding criterion is outside the current goal")
                workspace = uow.execution.workspace(run_id)
                if not workspace:
                    raise NotFoundError("Workspace missing")
                if report.source_ref:
                    ScopedFilesystem(workspace.path, workspace.policy).target(report.source_ref)
                finding = Finding(
                    id=finding_id,
                    run_id=run_id,
                    task_id=attempt.task_id,
                    criterion_id=report.criterion_id,
                    severity=report.severity,
                    category="external_worker",
                    summary=report.summary,
                    source_ref=report.source_ref,
                )
                uow.delivery.save_finding(finding)
                emit(
                    uow,
                    run,
                    EventType.FINDING_REPORTED,
                    receipt_key,
                    utc_now(),
                    EventPayload(
                        summary=finding.summary,
                        reason=fingerprint,
                        status=finding.severity,
                        criterion_id=finding.criterion_id,
                        finding_ids=(finding.id,),
                    ),
                    attempt.assigned_actor_session_id,
                    attempt.task_id,
                    attempt.id,
                )
                uow.commit()
                return finding
