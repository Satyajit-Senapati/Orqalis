from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, Field

from orqalis.domain.base import Entity, utc_now


class ActorType(StrEnum):
    ORCHESTRATOR = "ORCHESTRATOR"
    AGENT = "AGENT"


class AgentRole(StrEnum):
    REQUIREMENTS = "requirements"
    ARCHITECT = "architect"
    PLANNER = "planner"
    DEVELOPER = "developer"
    TESTER = "tester"
    REVIEWER = "reviewer"
    CHANGE_GUARDIAN = "change_guardian"
    REPAIR = "repair"
    DOCUMENTATION = "documentation"
    GITOPS = "gitops"
    MEMORY_CURATOR = "memory_curator"


class ActorStatus(StrEnum):
    STARTING = "STARTING"
    WORKING = "WORKING"
    WAITING_FOR_DEPENDENCY = "WAITING_FOR_DEPENDENCY"
    IDLE = "IDLE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class ActorSession(Entity):
    run_id: UUID
    actor_type: ActorType
    role: AgentRole | None = None
    provider: str | None = None
    model: str | None = None
    status: ActorStatus = ActorStatus.STARTING
    current_task_id: UUID | None = None
    started_at: AwareDatetime = Field(default_factory=utc_now)
    completed_at: AwareDatetime | None = None
    working_ms: int = Field(default=0, ge=0)
    waiting_ms: int = Field(default=0, ge=0)
    blocked_ms: int = Field(default=0, ge=0)
    loaded_skills: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    activity_summary: str | None = None
    tasks_attempted: int = Field(default=0, ge=0)
    tasks_completed: int = Field(default=0, ge=0)
    tasks_failed: int = Field(default=0, ge=0)
