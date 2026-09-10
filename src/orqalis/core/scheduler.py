from graphlib import TopologicalSorter
from uuid import UUID

from orqalis.domain.agent import AgentRole
from orqalis.domain.plan import TaskPlan
from orqalis.domain.task import Task, TaskStatus

WRITE_ROLES = frozenset({AgentRole.DEVELOPER, AgentRole.TESTER, AgentRole.DOCUMENTATION})


def ready_tasks(plan: TaskPlan) -> tuple[Task, ...]:
    succeeded = {task.id for task in plan.tasks if task.status == TaskStatus.SUCCEEDED}
    prerequisites: dict[UUID, set[UUID]] = {task.id: set() for task in plan.tasks}
    for edge in plan.dependencies:
        prerequisites[edge.task_id].add(edge.depends_on_task_id)
    return tuple(
        task
        for task in plan.tasks
        if task.status in {TaskStatus.PENDING, TaskStatus.READY}
        and prerequisites[task.id] <= succeeded
    )


def dispatch_wave(plan: TaskPlan, capacity: int) -> tuple[Task, ...]:
    if capacity < 1:
        return ()
    running = [task for task in plan.tasks if task.status == TaskStatus.RUNNING]
    available = max(0, capacity - len(running))
    writer_active = any(task.preferred_role in WRITE_ROLES for task in running)
    selected: list[Task] = []
    for task in ready_tasks(plan):
        if len(selected) >= available:
            break
        if task.preferred_role in WRITE_ROLES:
            if writer_active:
                continue
            writer_active = True
        selected.append(task)
    return tuple(selected)


def plan_completion(plan: TaskPlan) -> float:
    total = sum(task.work_weight for task in plan.tasks)
    succeeded = sum(task.work_weight for task in plan.tasks if task.status == TaskStatus.SUCCEEDED)
    # Skipped/cancelled tasks do not silently satisfy dependencies or acceptance.
    return 100 * succeeded / total


def ordered_tasks(plan: TaskPlan) -> tuple[Task, ...]:
    """Order a validated DAG by dependencies, independent of database row order."""
    graph: dict[UUID, set[UUID]] = {task.id: set() for task in plan.tasks}
    for edge in plan.dependencies:
        graph[edge.task_id].add(edge.depends_on_task_id)
    tasks = {task.id: task for task in plan.tasks}
    return tuple(tasks[task_id] for task_id in TopologicalSorter(graph).static_order())
