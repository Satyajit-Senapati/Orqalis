from typing import Protocol

from orqalis.domain.acceptance import GoalContract
from orqalis.domain.memory import ContextPack
from orqalis.domain.plan import TaskPlan


class PlannerAgent(Protocol):
    def plan(self, goal: GoalContract, context: ContextPack) -> TaskPlan: ...


def plan_identity(plan: TaskPlan) -> tuple[object, ...]:
    mutable = {"status", "ready_at", "started_at", "completed_at", "attempt_count"}
    return (
        plan.run_id,
        plan.goal_version_id,
        plan.version,
        sorted((str(task.id), task.model_dump_json(exclude=mutable)) for task in plan.tasks),
        sorted(edge.model_dump_json() for edge in plan.dependencies),
    )
