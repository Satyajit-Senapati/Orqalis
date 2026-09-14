import fnmatch
from uuid import uuid5

from orqalis.domain.acceptance import GoalContract
from orqalis.domain.agent import AgentRole
from orqalis.domain.memory import ContextPack
from orqalis.domain.plan import TaskPlan
from orqalis.domain.task import Task, TaskDependency


def implementation_capabilities(goal: GoalContract, context: ContextPack) -> tuple[str, ...]:
    """Route from explicit source scope, never from an unrelated repository language."""
    scopes = tuple(scope for scope in goal.goal.scope if not any(c.isspace() for c in scope))
    python = any(scope.endswith(".py") for scope in scopes) or any(
        path.endswith(".py")
        and any(
            fnmatch.fnmatchcase(path, scope) or (scope.endswith("/") and path.startswith(scope))
            for scope in scopes
        )
        for path in context.relevant_files
    )
    return ("python",) if python else ()


class VerticalPlanner:
    """Minimal deterministic Developer -> Test -> Reviewer DAG for a single slice."""

    def plan(self, goal: GoalContract, context: ContextPack, version: int = 1) -> TaskPlan:
        ids = tuple(criterion.id for criterion in goal.criteria)
        tasks = tuple(
            Task(
                id=uuid5(goal.goal.id, f"vertical:{version}:{role}"),
                run_id=goal.goal.run_id,
                plan_version=version,
                description=description,
                expected_outcome=outcome,
                preferred_role=role,
                validation_method=validation,
                acceptance_criterion_ids=ids,
                required_capabilities=("evidence_review",)
                if role == AgentRole.REVIEWER
                else implementation_capabilities(goal, context)
                if role == AgentRole.DEVELOPER
                else (),
            )
            for role, description, outcome, validation in (
                (
                    AgentRole.DEVELOPER,
                    goal.goal.goal,
                    "Implement the accepted scope with focused code and test changes",
                    "Acceptance validators",
                ),
                (
                    AgentRole.TESTER,
                    "Validate the current acceptance contract",
                    "Persist deterministic evidence for every executable criterion",
                    "Acceptance validators",
                ),
                (
                    AgentRole.REVIEWER,
                    "Review implementation against every acceptance criterion",
                    "Return evidence-backed PASS/FAIL for each criterion",
                    "Structured acceptance review",
                ),
            )
        )
        return TaskPlan(
            run_id=goal.goal.run_id,
            goal_version_id=goal.goal.id,
            version=version,
            tasks=tasks,
            dependencies=(
                TaskDependency(task_id=tasks[1].id, depends_on_task_id=tasks[0].id),
                TaskDependency(task_id=tasks[2].id, depends_on_task_id=tasks[1].id),
            ),
        )
