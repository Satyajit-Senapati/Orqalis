from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, Field

from orqalis.domain.agent import AgentRole
from orqalis.domain.base import Contract, Entity


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class Task(Entity):
    run_id: UUID
    # Introduction version; zero is preparatory work before an accepted goal/plan.
    plan_version: int = Field(default=1, ge=0)
    parent_task_id: UUID | None = None
    description: str = Field(min_length=1)
    expected_outcome: str = Field(min_length=1)
    status: TaskStatus = TaskStatus.PENDING
    risk: float = Field(default=0, ge=0, le=1)
    required_capabilities: tuple[str, ...] = ()
    preferred_role: AgentRole = AgentRole.DEVELOPER
    expected_artifacts: tuple[str, ...] = ()
    validation_method: str = Field(min_length=1)
    work_weight: float = Field(default=1, gt=0, allow_inf_nan=False)
    ready_at: AwareDatetime | None = None
    started_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None
    attempt_count: int = Field(default=0, ge=0)
    acceptance_criterion_ids: tuple[UUID, ...] = ()


class TaskDependency(Contract):
    task_id: UUID
    depends_on_task_id: UUID
    dependency_type: str = "finish_to_start"


class TaskExecution(Entity):
    run_id: UUID
    task_id: UUID
    attempt: int = Field(ge=1)
    assigned_actor_session_id: UUID
    ready_at: AwareDatetime | None = None
    started_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None
    status: TaskStatus = TaskStatus.PENDING
    queue_ms: int = Field(default=0, ge=0)
    active_ms: int = Field(default=0, ge=0)
    waiting_ms: int = Field(default=0, ge=0)
    blocked_ms: int = Field(default=0, ge=0)
    result_ref: UUID | None = None
