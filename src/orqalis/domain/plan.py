from graphlib import CycleError, TopologicalSorter
from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from orqalis.domain.base import Contract
from orqalis.domain.task import Task, TaskDependency


class TaskPlan(Contract):
    run_id: UUID
    goal_version_id: UUID
    version: int = Field(ge=1)
    tasks: tuple[Task, ...] = Field(min_length=1)
    dependencies: tuple[TaskDependency, ...] = ()

    @model_validator(mode="after")
    def validate_dag(self) -> Self:
        ids = {task.id for task in self.tasks}
        if len(ids) != len(self.tasks):
            raise ValueError("Task IDs must be unique")
        if any(
            task.run_id != self.run_id or task.plan_version > self.version for task in self.tasks
        ):
            raise ValueError("Tasks must belong to this run and cannot originate in a future plan")
        edges = {(edge.task_id, edge.depends_on_task_id) for edge in self.dependencies}
        if len(edges) != len(self.dependencies):
            raise ValueError("Duplicate dependencies")
        graph: dict[UUID, set[UUID]] = {task_id: set() for task_id in ids}
        for edge in self.dependencies:
            if edge.task_id not in ids or edge.depends_on_task_id not in ids:
                raise ValueError("Dependency references an unknown task")
            if edge.dependency_type != "finish_to_start":
                raise ValueError("Unsupported dependency type")
            graph[edge.task_id].add(edge.depends_on_task_id)
        try:
            tuple(TopologicalSorter(graph).static_order())
        except CycleError as exc:
            raise ValueError("Task plan contains a dependency cycle") from exc
        return self
