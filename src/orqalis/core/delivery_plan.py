from uuid import uuid5

from orqalis.domain.agent import AgentRole
from orqalis.domain.plan import TaskPlan
from orqalis.domain.task import Task, TaskDependency, TaskStatus

DELIVERY_STEPS = (
    ("implementation", AgentRole.CHANGE_GUARDIAN, "Inspect accepted implementation"),
    ("documentation", AgentRole.DOCUMENTATION, "Document accepted changes"),
    ("validation", AgentRole.TESTER, "Validate final deliverable"),
    ("final", AgentRole.CHANGE_GUARDIAN, "Inspect final deliverable"),
    ("git", AgentRole.GITOPS, "Deliver validated changes to Git"),
    ("memory", AgentRole.MEMORY_CURATOR, "Curate accepted project knowledge"),
)


def delivery_plan(current: TaskPlan) -> TaskPlan:
    version = current.version + 1
    tasks = tuple(
        Task(
            id=uuid5(current.run_id, f"delivery-task:{step}"),
            run_id=current.run_id,
            plan_version=version,
            description=description,
            expected_outcome=description,
            preferred_role=role,
            validation_method="Persisted delivery evidence",
        )
        for step, role, description in DELIVERY_STEPS
    )
    dependencies = [
        TaskDependency(task_id=tasks[0].id, depends_on_task_id=task.id)
        for task in current.tasks
        if task.status == TaskStatus.SUCCEEDED
    ]
    dependencies.extend(
        TaskDependency(task_id=child.id, depends_on_task_id=parent.id)
        for parent, child in zip(tasks, tasks[1:], strict=False)
    )
    return TaskPlan(
        run_id=current.run_id,
        goal_version_id=current.goal_version_id,
        version=version,
        tasks=(*current.tasks, *tasks),
        dependencies=(*current.dependencies, *dependencies),
    )
