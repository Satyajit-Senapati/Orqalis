from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from orqalis.persistence.models import Base


class WorkspaceRow(Base):
    __tablename__ = "run_workspaces"
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    path: Mapped[str] = mapped_column(Text)
    base_commit: Mapped[str] = mapped_column(String(64))
    branch: Mapped[str] = mapped_column(String(255))
    policy: Mapped[dict[str, object]] = mapped_column(JSON)


class ToolInvocationRow(Base):
    __tablename__ = "tool_invocations"
    __table_args__ = (UniqueConstraint("provider_invocation_id", "call_id"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    task_execution_id: Mapped[UUID] = mapped_column(ForeignKey("task_executions.id"), index=True)
    actor_session_id: Mapped[UUID] = mapped_column(ForeignKey("actor_sessions.id"))
    provider_invocation_id: Mapped[UUID] = mapped_column(ForeignKey("provider_executions.id"))
    call_id: Mapped[str] = mapped_column(String(255))
    tool: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observation: Mapped[dict[str, object] | None] = mapped_column(JSON)


class ReviewRow(Base):
    __tablename__ = "reviews"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    goal_version_id: Mapped[UUID] = mapped_column(ForeignKey("goal_versions.id"))
    plan_version: Mapped[int] = mapped_column(Integer)
    actor_session_id: Mapped[UUID] = mapped_column(ForeignKey("actor_sessions.id"))
    tree_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
