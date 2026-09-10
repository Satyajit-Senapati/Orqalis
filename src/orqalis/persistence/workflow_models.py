from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from orqalis.persistence.models import Base


class RunRow(Base):
    __tablename__ = "runs"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    request: Mapped[str] = mapped_column(Text)
    target_branch: Mapped[str] = mapped_column(String(255))
    base_commit: Mapped[str] = mapped_column(String(64))
    current_goal_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "goal_versions.id", use_alter=True, name="fk_runs_current_goal_version_id_goal_versions"
        )
    )
    state: Mapped[str] = mapped_column(String(64))
    ui_phase: Mapped[str] = mapped_column(String(32))
    repair_iteration: Mapped[int] = mapped_column(Integer)
    max_repair_iterations: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    plan_version: Mapped[int] = mapped_column(Integer)
    resume_state: Mapped[str | None] = mapped_column(String(64))
    last_event_sequence: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GoalRow(Base):
    __tablename__ = "goal_versions"
    __table_args__ = (UniqueConstraint("run_id", "version"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    goal: Mapped[str] = mapped_column(Text)
    scope: Mapped[list[str]] = mapped_column(JSON)
    out_of_scope: Mapped[list[str]] = mapped_column(JSON)
    constraints: Mapped[list[str]] = mapped_column(JSON)
    assumptions: Mapped[list[str]] = mapped_column(JSON)
    definition_of_done: Mapped[list[str]] = mapped_column(JSON)
    supersedes_goal_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("goal_versions.id"))
    revision_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CriterionRow(Base):
    __tablename__ = "acceptance_criteria"
    __table_args__ = (UniqueConstraint("goal_version_id", "key"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    goal_version_id: Mapped[UUID] = mapped_column(ForeignKey("goal_versions.id"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(16))
    validation_spec: Mapped[dict[str, object]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16))
    attempt_count: Mapped[int] = mapped_column(Integer)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_refs: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EvidenceRow(Base):
    __tablename__ = "evidence"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    criterion_id: Mapped[UUID] = mapped_column(ForeignKey("acceptance_criteria.id"), index=True)
    task_id: Mapped[UUID | None] = mapped_column(Uuid)
    task_execution_id: Mapped[UUID | None] = mapped_column(Uuid)
    evidence_type: Mapped[str] = mapped_column(String(64))
    artifact_ref: Mapped[UUID | None] = mapped_column(Uuid)
    structured_data: Mapped[dict[str, object]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
