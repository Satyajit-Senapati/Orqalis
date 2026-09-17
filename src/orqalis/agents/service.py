import asyncio
import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import UUID, uuid5

from pydantic import JsonValue

from orqalis.agents.roles import provider_output_schema
from orqalis.agents.routing import CapabilityRouter
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit, locked_run, require_key
from orqalis.domain.agent import AgentRole
from orqalis.domain.base import utc_now
from orqalis.domain.errors import ConflictError, NotFoundError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.memory import ContextPack, MemoryType
from orqalis.domain.provider import (
    ExecutionBudget,
    InvocationStatus,
    ProviderErrorCode,
    ProviderExecution,
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ToolDefinition,
    ToolObservation,
)
from orqalis.domain.run import RunState
from orqalis.domain.task import TaskStatus
from orqalis.observability.instrumentation import observed_async
from orqalis.providers.errors import ProviderError
from orqalis.providers.validation import validate_result

_ACTIVE_STATES = {
    RunState.ANALYZING,
    RunState.EXECUTING,
    RunState.TESTING,
    RunState.REVIEWING,
    RunState.CHANGE_GUARD,
    RunState.DOCUMENTING,
}


def _fingerprint(request: ProviderExecutionRequest, provider: str, model: str) -> str:
    data = request.model_dump(mode="json")
    task = request.task.model_dump(
        mode="json",
        exclude={
            "status",
            "ready_at",
            "started_at",
            "completed_at",
            "attempt_count",
        },
    )
    # Worktree-derived repository-map entries evolve as this attempt writes files.
    # They are inspection hints, not a new logical invocation contract. Keep durable
    # memory/history content bound while removing projection timestamps and freshness
    # fields that are expected to change when an interrupted worker is resumed.
    context = request.context.model_dump(
        mode="json",
        exclude={
            "items": True,
            "relevant_files": True,
            "freshness": {"dirty_paths", "fresh"},
            "confidence": True,
            "targeted_inspection_paths": True,
            "requires_inspection": True,
            "size_chars": True,
        },
    )
    freshness = context.get("freshness")
    if isinstance(freshness, dict):
        freshness.pop("active_items", None)
    durable_items = []
    for match in request.context.items:
        if match.item.type == MemoryType.REPOSITORY_MAP:
            continue
        value = match.model_dump(mode="json")
        item = value.get("item")
        if isinstance(item, dict):
            item.pop("created_at", None)
            item.pop("last_verified_at", None)
            item.pop("status", None)
        sources = value.get("sources")
        if isinstance(sources, list):
            for source in sources:
                if isinstance(source, dict):
                    source.pop("created_at", None)
        durable_items.append(value)
    context["durable_items"] = durable_items
    data.update(task=task, context=context, provider=provider, model=model)
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class AgentExecutionService:
    """Runs providers as workers; only Orchestrator changes task/workflow state."""

    def __init__(
        self,
        unit_of_work: Callable[[], ProjectUnitOfWork],
        router: CapabilityRouter,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.unit_of_work, self.router, self.clock = unit_of_work, router, clock

    @observed_async("agent.invoke")
    async def invoke(
        self,
        run_id: UUID,
        execution_id: UUID,
        provider_id: str,
        context: ContextPack,
        output_schema: dict[str, JsonValue],
        key: str,
        tools: tuple[ToolDefinition, ...] = (),
        budget: ExecutionBudget | None = None,
        observations: tuple[ToolObservation, ...] = (),
    ) -> ProviderExecutionResult:
        require_key(key)
        invocation_id = uuid5(run_id, f"provider:{key}")
        with self.unit_of_work() as uow:
            run = locked_run(uow, run_id)
            project = uow.projects.get(run.project_id)
            if project is None or context.project_id != run.project_id:
                raise NotFoundError("Provider context belongs to another project")
            if (
                provider_id != "auto"
                and project.settings.allowed_providers
                and provider_id not in (project.settings.allowed_providers)
            ):
                raise PolicyDeniedError("Provider is not permitted for this project")
            attempt = next(
                (item for item in uow.runtime.executions(run_id) if item.id == execution_id), None
            )
            plan = uow.runtime.get_plan(run_id, run.plan_version)
            if attempt is None:
                raise NotFoundError("Task execution or plan not found")
            task = next(
                (item for item in uow.runtime.tasks(run_id) if item.id == attempt.task_id), None
            )
            actor = next(
                (
                    item
                    for item in uow.runtime.actors(run_id)
                    if item.id == attempt.assigned_actor_session_id
                ),
                None,
            )
            goal = (
                uow.runs.get_goal(run.current_goal_version_id)
                if run.current_goal_version_id
                else None
            )
            if task is None or actor is None:
                raise NotFoundError("Execution contract not found")
            # Deterministic service roles cannot be invoked as provider workers even
            # through the low-level SDK entry point with a caller-supplied schema.
            provider_output_schema(task.preferred_role)
            preparing = task.preferred_role == AgentRole.REQUIREMENTS and task.plan_version == 0
            if preparing:
                if run.state != RunState.ANALYZING or tools:
                    raise PolicyDeniedError("Requirements are read-only preparatory work")
            elif goal is None or plan is None or run.state == RunState.ANALYZING:
                raise NotFoundError("Accepted goal and implementation plan are required")
            proofs = tuple(
                e
                for criterion in (goal.criteria if goal else ())
                for ref in criterion.evidence_refs
                if (e := uow.runs.get_evidence(ref)) is not None
            )
            workspace = uow.execution.workspace(run_id)
            constraints = (
                goal.goal.constraints
                if goal
                else ("Define testable acceptance for the user request; do not assert PASS.",)
            )
            if workspace:
                constraints = (
                    *constraints,
                    "Approved workspace policy: " + workspace.policy.model_dump_json(),
                )
            findings = (
                tuple(
                    finding
                    for finding in uow.delivery.findings(run_id)
                    if finding.category == "external_worker" and finding.status == "open"
                )
                if actor.role == AgentRole.REVIEWER
                else ()
            )
            if findings:
                constraints = (
                    *constraints,
                    "Independently evaluate every open worker finding in finding_reviews. "
                    "Resolution requires current passing evidence or verifiable source checks. "
                    "Unresolved blocking findings require overall FAIL "
                    "and actionable blocking_findings.",
                )
            provider, request = self.router.prepare(
                task,
                context,
                invocation_id,
                actor.id,
                attempt.id,
                provider_id,
                project.settings.permissions,
                output_schema,
                tools,
                project.settings.repository_profile.languages,
                project.settings.skill_pins,
                budget,
                observations,
                constraints,
                project.settings.allowed_providers,
                goal,
                proofs,
                findings,
            )
            resolved_provider_id = provider.descriptor.id
            fingerprint = _fingerprint(request, resolved_provider_id, provider.descriptor.model)
            existing = uow.providers.get(invocation_id)
            if existing:
                if existing.request_hash != fingerprint:
                    raise ConflictError("Invocation key belongs to a different request")
                if existing.status == InvocationStatus.SUCCEEDED and existing.result:
                    return existing.result
                if existing.status == InvocationStatus.RUNNING:
                    if existing.deadline_at >= self.clock():
                        raise ConflictError("Invocation is already in progress")
                    self._finish(uow, existing, None, ProviderErrorCode.INTERRUPTED)
                    uow.commit()
                    raise ProviderError(ProviderErrorCode.INTERRUPTED)
                raise ProviderError(existing.error_code or ProviderErrorCode.INTERNAL)
            if (
                run.state not in _ACTIVE_STATES
                or attempt.status != TaskStatus.RUNNING
                or (
                    not preparing
                    and (plan is None or plan.goal_version_id != run.current_goal_version_id)
                )
            ):
                raise ConflictError("Provider invocation requires active work on the current goal")
            at = self.clock()
            invocation = ProviderExecution(
                id=invocation_id,
                run_id=run_id,
                task_execution_id=attempt.id,
                actor_session_id=actor.id,
                provider=resolved_provider_id,
                model=provider.descriptor.model,
                request_hash=fingerprint,
                idempotency_key=key,
                started_at=at,
                created_at=at,
                deadline_at=at + timedelta(seconds=request.budget.timeout_seconds),
            )
            uow.providers.save(invocation)
            skill_refs = tuple(
                f"{skill.metadata.id}@{skill.metadata.version}" for skill in request.selected_skills
            )
            uow.runtime.save_actor(
                actor.model_copy(
                    update={
                        "provider": resolved_provider_id,
                        "model": provider.descriptor.model,
                        "loaded_skills": skill_refs,
                        "allowed_tools": tuple(tool.name.value for tool in request.allowed_tools),
                    }
                )
            )
            if skill_refs:
                emit(
                    uow,
                    run,
                    EventType.SKILL_LOADED,
                    f"provider:{key}:skills",
                    at,
                    EventPayload(skill_refs=skill_refs),
                    actor.id,
                    task.id,
                    attempt.id,
                )
            emit(
                uow,
                run,
                EventType.PROVIDER_INVOCATION_STARTED,
                f"provider:{key}:start",
                at,
                EventPayload(
                    provider_execution_id=invocation.id,
                    status=invocation.status,
                    skill_refs=skill_refs,
                    memory_ids=tuple(match.item.id for match in context.items),
                    summary=(
                        f"Context: {len(context.items)} memory references; "
                        f"indexed commit {context.freshness.indexed_commit or 'unindexed'}; "
                        "targeted inspection "
                        f"{'required' if context.requires_inspection else 'not required'}"
                    ),
                ),
                actor.id,
                task.id,
                attempt.id,
            )
            uow.commit()
        result = None
        error = None
        cancelled = False
        try:
            async with asyncio.timeout(request.budget.timeout_seconds):
                result = validate_result(request, await provider.execute(request))
        except asyncio.CancelledError:
            error, cancelled = ProviderErrorCode.CANCELLED, True
        except TimeoutError:
            error = ProviderErrorCode.TIMEOUT
        except ProviderError as failure:
            error = failure.error_code
        except Exception:
            # Raw SDK exceptions may include credentials, prompts or reasoning.
            error = ProviderErrorCode.INTERNAL
        with self.unit_of_work() as uow:
            run = locked_run(uow, run_id)
            current = uow.providers.get(invocation_id)
            assert current is not None
            if current.status != InvocationStatus.RUNNING:
                raise ProviderError(current.error_code or ProviderErrorCode.INTERRUPTED)
            attempt = next(
                item for item in uow.runtime.executions(run_id) if item.id == execution_id
            )
            if run.state not in _ACTIVE_STATES or attempt.status != TaskStatus.RUNNING:
                result, error = None, ProviderErrorCode.CANCELLED
            self._finish(uow, current, result, error)
            uow.commit()
        if cancelled:
            raise asyncio.CancelledError
        if error:
            raise ProviderError(error)
        assert result is not None
        return result

    def _finish(
        self,
        uow: ProjectUnitOfWork,
        invocation: ProviderExecution,
        result: ProviderExecutionResult | None,
        error: ProviderErrorCode | None,
    ) -> None:
        run = locked_run(uow, invocation.run_id)
        status = (
            InvocationStatus.SUCCEEDED
            if error is None
            else {
                ProviderErrorCode.CANCELLED: InvocationStatus.CANCELLED,
                ProviderErrorCode.INTERRUPTED: InvocationStatus.INTERRUPTED,
            }.get(error, InvocationStatus.FAILED)
        )
        at = max(self.clock(), invocation.started_at)
        uow.providers.save(
            invocation.model_copy(
                update={
                    "status": status,
                    "completed_at": at,
                    "result": result,
                    "error_code": error,
                }
            )
        )
        emit(
            uow,
            run,
            EventType.PROVIDER_INVOCATION_COMPLETED,
            f"provider:{invocation.idempotency_key}:finish",
            at,
            EventPayload(
                provider_execution_id=invocation.id,
                status=status,
                reason=error.value if error else None,
            ),
            actor_id=invocation.actor_session_id,
            execution_id=invocation.task_execution_id,
        )
