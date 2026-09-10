from uuid import UUID, uuid5

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from orqalis.domain.agent import ActorSession
from orqalis.domain.errors import ConflictError
from orqalis.domain.plan import TaskPlan
from orqalis.domain.task import Task, TaskDependency, TaskExecution
from orqalis.domain.timing import PhaseExecution
from orqalis.persistence.runtime_models import (
    ActorRow,
    DependencyRow,
    PhaseRow,
    PlanRow,
    PlanTaskRow,
    TaskExecutionRow,
    TaskRow,
)


def task_values(task: Task) -> dict[str, object]:
    return {
        **task.model_dump(exclude={"acceptance_criterion_ids"}),
        "acceptance_criterion_ids": [str(key) for key in task.acceptance_criterion_ids],
    }


class SQLRuntimeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_task(self, task: Task) -> None:
        self.session.add(TaskRow(**task_values(task)))
        self.session.flush()

    def tasks(self, run_id: UUID) -> tuple[Task, ...]:
        return tuple(
            Task.model_validate(row, from_attributes=True)
            for row in self.session.scalars(
                select(TaskRow)
                .where(TaskRow.run_id == run_id)
                .order_by(TaskRow.created_at, TaskRow.id)
            )
        )

    def save_plan(self, plan: TaskPlan) -> None:
        self.session.add(
            PlanRow(
                id=uuid5(plan.run_id, f"plan:{plan.version}"),
                run_id=plan.run_id,
                goal_version_id=plan.goal_version_id,
                version=plan.version,
            )
        )
        self.session.flush()
        for task in plan.tasks:
            existing = self.session.get(TaskRow, task.id)
            if existing is None:
                self.session.add(TaskRow(**task_values(task)))
            elif Task.model_validate(existing, from_attributes=True) != task:
                raise ConflictError("Plan revisions cannot rewrite existing task records")
        self.session.flush()
        for task in plan.tasks:
            self.session.add(
                PlanTaskRow(plan_id=uuid5(plan.run_id, f"plan:{plan.version}"), task_id=task.id)
            )
        for edge in plan.dependencies:
            existing_edge = self.session.get(DependencyRow, (edge.task_id, edge.depends_on_task_id))
            if existing_edge is None:
                self.session.add(DependencyRow(**edge.model_dump()))
        self.session.flush()

    def get_plan(self, run_id: UUID, version: int) -> TaskPlan | None:
        row = self.session.scalar(
            select(PlanRow).where(PlanRow.run_id == run_id, PlanRow.version == version)
        )
        if row is None:
            return None
        tasks = tuple(
            Task.model_validate(task, from_attributes=True)
            for task in self.session.scalars(
                select(TaskRow)
                .join(PlanTaskRow, PlanTaskRow.task_id == TaskRow.id)
                .where(PlanTaskRow.plan_id == row.id)
                .order_by(TaskRow.created_at, TaskRow.id)
            )
        )
        ids = [task.id for task in tasks]
        dependencies = tuple(
            TaskDependency.model_validate(edge, from_attributes=True)
            for edge in self.session.scalars(
                select(DependencyRow)
                .where(DependencyRow.task_id.in_(ids), DependencyRow.depends_on_task_id.in_(ids))
                .order_by(DependencyRow.task_id, DependencyRow.depends_on_task_id)
            )
        )
        return TaskPlan(
            run_id=run_id,
            goal_version_id=row.goal_version_id,
            version=version,
            tasks=tasks,
            dependencies=dependencies,
        )

    def save_task(self, task: Task) -> None:
        self.session.execute(
            update(TaskRow).where(TaskRow.id == task.id).values(**task_values(task))
        )

    def actors(self, run_id: UUID) -> tuple[ActorSession, ...]:
        return tuple(
            ActorSession.model_validate(row, from_attributes=True)
            for row in self.session.scalars(
                select(ActorRow)
                .where(ActorRow.run_id == run_id)
                .order_by(ActorRow.started_at, ActorRow.id)
            )
        )

    def save_actor(self, actor: ActorSession) -> None:
        self.session.merge(ActorRow(**actor.model_dump()))
        self.session.flush()

    def executions(self, run_id: UUID) -> tuple[TaskExecution, ...]:
        return tuple(
            TaskExecution.model_validate(row, from_attributes=True)
            for row in self.session.scalars(
                select(TaskExecutionRow)
                .where(TaskExecutionRow.run_id == run_id)
                .order_by(TaskExecutionRow.created_at, TaskExecutionRow.id)
            )
        )

    def save_execution(self, execution: TaskExecution) -> None:
        self.session.merge(TaskExecutionRow(**execution.model_dump()))
        self.session.flush()

    def phases(self, run_id: UUID) -> tuple[PhaseExecution, ...]:
        return tuple(
            PhaseExecution.model_validate(row, from_attributes=True)
            for row in self.session.scalars(
                select(PhaseRow)
                .where(PhaseRow.run_id == run_id)
                .order_by(PhaseRow.started_at, PhaseRow.id)
            )
        )

    def save_phase(self, phase: PhaseExecution) -> None:
        self.session.merge(PhaseRow(**phase.model_dump()))
        self.session.flush()
