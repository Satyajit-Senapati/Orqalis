from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, Field

from orqalis.domain.base import Entity


class RunState(StrEnum):
    RECEIVED = "RECEIVED"
    CONTEXT_SYNC = "CONTEXT_SYNC"
    ANALYZING = "ANALYZING"
    GOAL_DEFINED = "GOAL_DEFINED"
    PLANNED = "PLANNED"
    EXECUTING = "EXECUTING"
    INTEGRATING = "INTEGRATING"
    TESTING = "TESTING"
    REVIEWING = "REVIEWING"
    REPAIR_PLANNING = "REPAIR_PLANNING"
    CHANGE_GUARD = "CHANGE_GUARD"
    DOCUMENTING = "DOCUMENTING"
    DELIVERY_VALIDATION = "DELIVERY_VALIDATION"
    COMMITTING = "COMMITTING"
    PUSHING = "PUSHING"
    MEMORY_FINALIZATION = "MEMORY_FINALIZATION"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"


class UIPhase(StrEnum):
    CONTEXT = "CONTEXT"
    GOAL = "GOAL"
    PLAN = "PLAN"
    IMPLEMENT = "IMPLEMENT"
    TEST = "TEST"
    REVIEW = "REVIEW"
    REPAIR = "REPAIR"
    DOCS = "DOCS"
    DELIVER = "DELIVER"


class Run(Entity):
    project_id: UUID
    request: str = Field(min_length=1)
    target_branch: str = Field(min_length=1)
    base_commit: str = Field(min_length=1)
    current_goal_version_id: UUID | None = None
    state: RunState = RunState.RECEIVED
    ui_phase: UIPhase = UIPhase.CONTEXT
    repair_iteration: int = Field(default=0, ge=0)
    max_repair_iterations: int = Field(default=5, ge=0)
    started_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None
    plan_version: int = Field(default=0, ge=0)
    resume_state: RunState | None = None
    last_event_sequence: int = Field(default=0, ge=0)
