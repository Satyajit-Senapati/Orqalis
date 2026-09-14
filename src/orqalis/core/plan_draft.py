"""Build an editable next-version draft without mutating an approved plan."""

from uuid import uuid4

from orqalis.domain.plan import TaskPlan
from orqalis.domain.task import TaskDependency, TaskStatus


def draft_replacement(current: TaskPlan) -> TaskPlan:
    active = tuple(task for task in current.tasks if task.plan_version > 0)
    identities = {task.id: uuid4() for task in active}
    tasks = tuple(
        task.model_copy(
            update={
                "id": identities[task.id],
                "plan_version": current.version + 1,
                "status": TaskStatus.PENDING,
                "ready_at": None,
                "started_at": None,
                "completed_at": None,
                "attempt_count": 0,
            }
        )
        for task in active
    )
    dependencies = tuple(
        TaskDependency(
            task_id=identities[edge.task_id],
            depends_on_task_id=identities[edge.depends_on_task_id],
            dependency_type=edge.dependency_type,
        )
        for edge in current.dependencies
        if edge.task_id in identities and edge.depends_on_task_id in identities
    )
    return TaskPlan(
        run_id=current.run_id,
        goal_version_id=current.goal_version_id,
        version=current.version + 1,
        tasks=tasks,
        dependencies=dependencies,
    )
