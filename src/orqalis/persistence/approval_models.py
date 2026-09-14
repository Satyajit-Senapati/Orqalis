"""Persisted operator policy, approval requests, and immutable decisions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from orqalis.persistence.models import Base


class ControlPolicyRow(Base):
    __tablename__ = "run_control_policies"

    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    mode: Mapped[str] = mapped_column(String(32))
    gates: Mapped[list[str]] = mapped_column(JSON)


class ApprovalRequestRow(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "stage", "subject_version", "subject_digest", name="uq_approval_subject"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    stage: Mapped[str] = mapped_column(String(32))
    subject_version: Mapped[int] = mapped_column(Integer)
    subject_digest: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ApprovalDecisionRow(Base):
    __tablename__ = "approval_decisions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("approval_requests.id"), unique=True)
    decision: Mapped[str] = mapped_column(String(16))
    actor: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
