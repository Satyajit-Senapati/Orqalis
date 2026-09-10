from uuid import UUID

from pydantic import AwareDatetime, Field

from orqalis.domain.base import Contract, Entity
from orqalis.domain.run import UIPhase
from orqalis.domain.task import TaskStatus


class PhaseExecution(Entity):
    run_id: UUID
    phase: UIPhase
    iteration: int = Field(default=1, ge=1)
    started_at: AwareDatetime
    completed_at: AwareDatetime | None = None
    status: TaskStatus = TaskStatus.RUNNING
    active_ms: int = Field(default=0, ge=0)
    waiting_ms: int = Field(default=0, ge=0)
    blocked_ms: int = Field(default=0, ge=0)


class TimingBreakdown(Contract):
    wall_ms: int = Field(default=0, ge=0)
    active_ms: int = Field(default=0, ge=0)
    waiting_ms: int = Field(default=0, ge=0)
    blocked_ms: int = Field(default=0, ge=0)
    idle_ms: int = Field(default=0, ge=0)
    queue_ms: int = Field(default=0, ge=0)
