import asyncio
from collections.abc import Callable
from uuid import UUID

from orqalis.agents.service import AgentExecutionService
from orqalis.core.goals import GoalService
from orqalis.core.orchestrator import Orchestrator
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import locked_run
from orqalis.domain.acceptance import GoalContract, GoalDraft
from orqalis.domain.errors import ConflictError, NotFoundError, OrqalisError
from orqalis.domain.run import RunState
from orqalis.domain.task import TaskStatus
from orqalis.execution.cancellation import watch_cancellation
from orqalis.memory.service import MemoryService


class RequirementsCoordinator:
    def __init__(
        self,
        factory: Callable[[], ProjectUnitOfWork],
        orchestrator: Orchestrator,
        goals: GoalService,
        memory: MemoryService,
        agents: AgentExecutionService,
    ) -> None:
        self.factory, self.orchestrator, self.goals = factory, orchestrator, goals
        self.memory, self.agents = memory, agents

    async def define(self, run_id: UUID, provider_id: str) -> GoalContract:
        with self.factory() as lease:
            if not lease.execution.try_run_lock(run_id):
                raise ConflictError("Another controller owns this run")
            return await watch_cancellation(self.factory, run_id, self._define(run_id, provider_id))

    async def _define(self, run_id: UUID, provider_id: str) -> GoalContract:
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            project = uow.projects.get(run.project_id)
            if project is None:
                raise NotFoundError("Project missing")
            if run.state == RunState.GOAL_DEFINED:
                return self.goals.get(run_id)
            if run.state != RunState.ANALYZING:
                raise ConflictError("Resume the run to ANALYZING before defining requirements")
        attempt = self.orchestrator.start_requirements(run_id)
        try:
            if not run.current_goal_version_id:
                context = self.memory.context(project, run.request)
                result = await self.agents.invoke(
                    run_id,
                    attempt.id,
                    provider_id,
                    context,
                    GoalDraft.model_json_schema(),
                    f"requirements:{attempt.id}",
                )
                if result.output is None:
                    raise ConflictError("Requirements must return a structured goal")
                goal = self.goals.define_initial(
                    run_id, attempt.id, GoalDraft.model_validate(result.output)
                )
            else:
                goal = self.goals.get(run_id)
            if attempt.status != TaskStatus.SUCCEEDED:
                self.orchestrator.transition_task(
                    run_id, attempt.id, TaskStatus.SUCCEEDED, f"requirements:finished:{attempt.id}"
                )
            self.orchestrator.advance(run_id, RunState.GOAL_DEFINED, "prepare:goal")
            return goal
        except (OrqalisError, asyncio.CancelledError):
            with self.factory() as uow:
                current = locked_run(uow, run_id)
            if current.state not in {RunState.CANCELLED, RunState.FAILED, RunState.COMPLETED}:
                self.orchestrator.transition_task(
                    run_id, attempt.id, TaskStatus.BLOCKED, f"requirements:blocked:{attempt.id}"
                )
                self.orchestrator.advance(
                    run_id, RunState.BLOCKED, f"requirements:blocked:{attempt.id}"
                )
            raise
