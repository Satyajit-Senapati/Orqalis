"""Operator approval contracts, separate from acceptance evidence."""

from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from orqalis.domain.base import Contract, Entity


class ControlMode(StrEnum):
    AUTONOMOUS = "AUTONOMOUS"
    SUPERVISED = "SUPERVISED"


class ApprovalStage(StrEnum):
    GOAL = "GOAL"
    PLAN = "PLAN"
    TASK = "TASK"
    REPAIR = "REPAIR"
    DELIVERY = "DELIVERY"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalDecisionKind(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


SUPERVISED_GATES = frozenset(
    {ApprovalStage.GOAL, ApprovalStage.PLAN, ApprovalStage.REPAIR, ApprovalStage.DELIVERY}
)


class ControlPolicy(Contract):
    run_id: UUID
    mode: ControlMode = ControlMode.AUTONOMOUS
    gates: frozenset[ApprovalStage] = frozenset()

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.mode == ControlMode.AUTONOMOUS and self.gates:
            raise ValueError("Autonomous mode cannot declare approval gates")
        return self

    def requires(self, stage: ApprovalStage) -> bool:
        return self.mode == ControlMode.SUPERVISED and stage in self.gates


class ApprovalDecision(Entity):
    request_id: UUID
    decision: ApprovalDecisionKind
    actor: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=1000)


class ApprovalRequest(Entity):
    run_id: UUID
    stage: ApprovalStage
    subject_version: int = Field(ge=0)
    subject_digest: str = Field(min_length=1, max_length=255)
    reason: str = Field(default="", max_length=1000)
    status: ApprovalStatus = ApprovalStatus.PENDING
    decision: ApprovalDecision | None = None
