from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from orqalis.persistence.models import Base


class GuardianRow(Base):
    __tablename__ = "change_guard_reports"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    actor_session_id: Mapped[UUID] = mapped_column(ForeignKey("actor_sessions.id"))
    tree_hash: Mapped[str] = mapped_column(String(64))
    passed: Mapped[bool] = mapped_column(Boolean)
    checkpoint: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FinalValidationRow(Base):
    __tablename__ = "final_validations"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    actor_session_id: Mapped[UUID] = mapped_column(ForeignKey("actor_sessions.id"))
    goal_version_id: Mapped[UUID] = mapped_column(ForeignKey("goal_versions.id"))
    tree_hash: Mapped[str] = mapped_column(String(64))
    passed: Mapped[bool] = mapped_column(Boolean)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GitDeliveryRow(Base):
    __tablename__ = "git_deliveries"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), unique=True)
    base_commit: Mapped[str] = mapped_column(String(64))
    branch: Mapped[str] = mapped_column(String(255))
    tree_hash: Mapped[str] = mapped_column(String(64))
    git_tree_sha: Mapped[str] = mapped_column(String(64))
    commit_message: Mapped[str] = mapped_column(Text)
    commit_attached: Mapped[bool] = mapped_column(Boolean)
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    push_status: Mapped[str] = mapped_column(String(32))
    remote: Mapped[str | None] = mapped_column(String(255))
    policy: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArtifactRow(Base):
    __tablename__ = "artifacts"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey("tasks.id"))
    type: Mapped[str] = mapped_column(String(64))
    path_or_uri: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FindingRow(Base):
    __tablename__ = "findings"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey("tasks.id"))
    criterion_id: Mapped[UUID | None] = mapped_column(ForeignKey("acceptance_criteria.id"))
    severity: Mapped[str] = mapped_column(String(32))
    category: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(Text)
    source_ref: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
