from collections.abc import Callable
from uuid import UUID

from pydantic import JsonValue

from orqalis.agents.roles import effective_tools
from orqalis.agents.service import AgentExecutionService
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.domain.errors import NotFoundError, PolicyDeniedError
from orqalis.domain.memory import ContextPack
from orqalis.domain.provider import ToolObservation
from orqalis.execution.cancellation import at_checkpoint
from orqalis.execution.tool_definitions import tool_definitions
from orqalis.execution.tools import ToolService


class AgentWorker:
    def __init__(
        self,
        factory: Callable[[], ProjectUnitOfWork],
        agents: AgentExecutionService,
        tools: ToolService,
    ) -> None:
        self.factory, self.agents, self.tools = factory, agents, tools

    async def execute(
        self,
        run_id: UUID,
        attempt_id: UUID,
        provider_id: str,
        context: ContextPack,
        schema: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        with self.factory() as uow:
            run = uow.runs.get(run_id)
            workspace = uow.execution.workspace(run_id)
            project = uow.projects.get(run.project_id) if run else None
            attempt = next(
                (item for item in uow.runtime.executions(run_id) if item.id == attempt_id), None
            )
            actor = next(
                (
                    item
                    for item in uow.runtime.actors(run_id)
                    if attempt and item.id == attempt.assigned_actor_session_id
                ),
                None,
            )
            if workspace is None or project is None or actor is None or actor.role is None:
                raise NotFoundError("Worker execution contract missing")
            definitions = tool_definitions(
                effective_tools(actor.role, project.settings.permissions)
            )
        observations: tuple[ToolObservation, ...] = ()
        for turn in range(workspace.policy.max_provider_turns):
            key = f"worker:{attempt_id}:{turn}"
            result = await self.agents.invoke(
                run_id,
                attempt_id,
                provider_id,
                context,
                schema,
                key,
                definitions,
                observations=observations,
            )
            if result.output is not None:
                return result.output
            with self.factory() as uow:
                invocation = next(
                    item for item in uow.providers.list(run_id) if item.idempotency_key == key
                )
            batch = []
            for call in result.tool_calls:
                observed = await at_checkpoint(self.tools.execute, invocation.id, call)
                batch.append(observed)
            observations = (*observations, *batch)
        raise PolicyDeniedError("Provider turn budget exhausted")
