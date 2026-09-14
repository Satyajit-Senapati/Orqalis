from uuid import UUID

from pydantic import JsonValue

from orqalis.agents.roles import effective_tools, role_definition
from orqalis.domain.acceptance import GoalContract
from orqalis.domain.artifact import Evidence, Finding
from orqalis.domain.capabilities import PermissionProfile
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.domain.memory import ContextPack
from orqalis.domain.provider import (
    ExecutionBudget,
    ProviderErrorCode,
    ProviderExecutionRequest,
    ToolDefinition,
    ToolObservation,
)
from orqalis.domain.task import Task
from orqalis.providers.errors import ProviderError
from orqalis.providers.ports import AgentProvider
from orqalis.providers.validation import check_schema, prompt_input
from orqalis.skills.registry import SkillRegistry


class CapabilityRouter:
    def __init__(self, skills: SkillRegistry, providers: tuple[AgentProvider, ...]) -> None:
        self.skills = skills
        self.providers = {provider.descriptor.id: provider for provider in providers}
        if len(self.providers) != len(providers):
            raise ConflictError("Provider IDs must be unique")

    def prepare(
        self,
        task: Task,
        context: ContextPack,
        invocation_id: UUID,
        actor_id: UUID,
        execution_id: UUID,
        provider_id: str,
        policy: PermissionProfile,
        output_schema: dict[str, JsonValue],
        tools: tuple[ToolDefinition, ...] = (),
        tags: tuple[str, ...] = (),
        pins: dict[str, str] | None = None,
        budget: ExecutionBudget | None = None,
        observations: tuple[ToolObservation, ...] = (),
        constraints: tuple[str, ...] = (),
        allowed_providers: tuple[str, ...] = (),
        acceptance: GoalContract | None = None,
        evidence: tuple[Evidence, ...] = (),
        findings: tuple[Finding, ...] = (),
    ) -> tuple[AgentProvider, ProviderExecutionRequest]:
        permitted = effective_tools(task.preferred_role, policy)
        if any(tool.name not in permitted for tool in tools):
            raise PolicyDeniedError("Role/project policy does not grant a requested tool")
        # Scope-derived capabilities also serve as applicability tags. Repository-wide
        # language tags alone can be stale or describe unrelated parts of a monorepo.
        applicable_tags = tuple(dict.fromkeys((*tags, *task.required_capabilities)))
        selected = self.skills.select(
            task.required_capabilities,
            tuple(tool.name for tool in tools),
            applicable_tags,
            role_definition(task.preferred_role).capabilities,
            pins,
        )
        check_schema(output_schema)
        budget = budget or ExecutionBudget()
        if provider_id == "auto":
            # Project allowlist order is the explicit preference order. Without one,
            # configured adapter order is stable. Fixture providers opt out.
            candidate_ids = allowed_providers or tuple(self.providers)
            candidates = tuple(
                provider
                for candidate_id in candidate_ids
                if (provider := self.providers.get(candidate_id)) is not None
                and provider.descriptor.available
                and provider.descriptor.auto_selectable
            )
        else:
            if allowed_providers and provider_id not in allowed_providers:
                raise PolicyDeniedError("Provider is not permitted for this project")
            provider = self.providers.get(provider_id)
            candidates = (
                (provider,) if provider is not None and provider.descriptor.available else ()
            )
        if not candidates:
            raise ProviderError(ProviderErrorCode.UNAVAILABLE)
        budget_exceeded = False
        for provider in candidates:
            if "structured_output" not in provider.descriptor.capabilities or (
                tools and "tool_calls" not in provider.descriptor.capabilities
            ):
                continue
            candidate_budget = budget
            if budget.max_input_chars > provider.descriptor.max_input_chars:
                candidate_budget = budget.model_copy(
                    update={"max_input_chars": provider.descriptor.max_input_chars}
                )
            request = ProviderExecutionRequest(
                invocation_id=invocation_id,
                run_id=task.run_id,
                actor_session_id=actor_id,
                task_execution_id=execution_id,
                role=task.preferred_role,
                task=task,
                context=context,
                selected_skills=selected,
                allowed_tools=tools,
                output_schema=output_schema,
                budget=candidate_budget,
                observations=observations,
                constraints=constraints,
                acceptance=acceptance,
                evidence=evidence,
                findings=findings,
            )
            try:
                prompt_input(request)
            except ProviderError as error:
                if provider_id != "auto" or error.error_code != ProviderErrorCode.BUDGET:
                    raise
                budget_exceeded = True
                continue
            return provider, request
        raise ProviderError(
            ProviderErrorCode.BUDGET if budget_exceeded else ProviderErrorCode.UNAVAILABLE
        )
