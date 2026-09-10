from uuid import UUID

from pydantic import JsonValue

from orqalis.agents.roles import effective_tools, role_definition
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
    ) -> tuple[AgentProvider, ProviderExecutionRequest]:
        provider = self.providers.get(provider_id)
        if provider is None or not provider.descriptor.available:
            raise ProviderError(ProviderErrorCode.UNAVAILABLE)
        permitted = effective_tools(task.preferred_role, policy)
        if any(tool.name not in permitted for tool in tools):
            raise PolicyDeniedError("Role/project policy does not grant a requested tool")
        if tools and "tool_calls" not in provider.descriptor.capabilities:
            raise ProviderError(ProviderErrorCode.UNAVAILABLE)
        selected = self.skills.select(
            task.required_capabilities,
            tuple(tool.name for tool in tools),
            tags,
            role_definition(task.preferred_role).capabilities,
            pins,
        )
        check_schema(output_schema)
        budget = budget or ExecutionBudget()
        if budget.max_input_chars > provider.descriptor.max_input_chars:
            budget = budget.model_copy(
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
            budget=budget,
            observations=observations,
            constraints=constraints,
        )
        prompt_input(request)
        return provider, request
