from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from orqalis.persistence.models import Base


class PlanRow(Base):
    __tablename__ = "plans"
    __table_args__ = (UniqueConstraint("run_id", "version"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    goal_version_id: Mapped[UUID] = mapped_column(ForeignKey("goal_versions.id"))
    version: Mapped[int] = mapped_column(Integer)


class TaskRow(Base):
    __tablename__ = "tasks"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    plan_version: Mapped[int] = mapped_column(Integer)
    parent_task_id: Mapped[UUID | None] = mapped_column(ForeignKey("tasks.id"))
    description: Mapped[str] = mapped_column(Text)
    expected_outcome: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    risk: Mapped[float] = mapped_column(Float)
    required_capabilities: Mapped[list[str]] = mapped_column(JSON)
    preferred_role: Mapped[str] = mapped_column(String(64))
    expected_artifacts: Mapped[list[str]] = mapped_column(JSON)
    validation_method: Mapped[str] = mapped_column(Text)
    work_weight: Mapped[float] = mapped_column(Float)
    acceptance_criterion_ids: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer)


class DependencyRow(Base):
    __tablename__ = "task_dependencies"
    task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    depends_on_task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    dependency_type: Mapped[str] = mapped_column(String(32))


class ActorRow(Base):
    __tablename__ = "actor_sessions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    actor_type: Mapped[str] = mapped_column(String(32))
    role: Mapped[str | None] = mapped_column(String(64))
    provider: Mapped[str | None] = mapped_column(String(255))
    model: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64))
    current_task_id: Mapped[UUID | None] = mapped_column(ForeignKey("tasks.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    working_ms: Mapped[int] = mapped_column(Integer)
    waiting_ms: Mapped[int] = mapped_column(Integer)
    blocked_ms: Mapped[int] = mapped_column(Integer)
    tasks_attempted: Mapped[int] = mapped_column(Integer)
    tasks_completed: Mapped[int] = mapped_column(Integer)
    tasks_failed: Mapped[int] = mapped_column(Integer)
    loaded_skills: Mapped[list[str]] = mapped_column(JSON)
    allowed_tools: Mapped[list[str]] = mapped_column(JSON)
    activity_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TaskExecutionRow(Base):
    __tablename__ = "task_executions"
    __table_args__ = (UniqueConstraint("task_id", "attempt"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    attempt: Mapped[int] = mapped_column(Integer)
    assigned_actor_session_id: Mapped[UUID] = mapped_column(ForeignKey("actor_sessions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32))
    queue_ms: Mapped[int] = mapped_column(Integer)
    active_ms: Mapped[int] = mapped_column(Integer)
    waiting_ms: Mapped[int] = mapped_column(Integer)
    blocked_ms: Mapped[int] = mapped_column(Integer)
    result_ref: Mapped[UUID | None] = mapped_column(Uuid)


class PhaseRow(Base):
    __tablename__ = "phase_executions"
    __table_args__ = (UniqueConstraint("run_id", "phase", "iteration"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    phase: Mapped[str] = mapped_column(String(32))
    iteration: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32))
    active_ms: Mapped[int] = mapped_column(Integer)
    waiting_ms: Mapped[int] = mapped_column(Integer)
    blocked_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventRow(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_events_run_sequence"),
        UniqueConstraint("run_id", "idempotency_key", name="uq_events_run_idempotency"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    phase: Mapped[str | None] = mapped_column(String(32))
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey("tasks.id"))
    task_execution_id: Mapped[UUID | None] = mapped_column(ForeignKey("task_executions.id"))
    actor_session_id: Mapped[UUID | None] = mapped_column(ForeignKey("actor_sessions.id"))
    correlation_id: Mapped[UUID | None] = mapped_column(Uuid)
    causation_id: Mapped[UUID | None] = mapped_column(ForeignKey("events.id"))
    status: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    trace_id: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PlanTaskRow(Base):
    __tablename__ = "plan_tasks"
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plans.id"), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
