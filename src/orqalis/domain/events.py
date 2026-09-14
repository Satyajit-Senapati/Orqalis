from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, Field

from orqalis.domain.base import Contract, Entity


class EventType(StrEnum):
    RUN_CREATED = "RUN_CREATED"
    RUN_STARTED = "RUN_STARTED"
    RUN_STATE_CHANGED = "RUN_STATE_CHANGED"
    RUN_PAUSED = "RUN_PAUSED"
    RUN_RESUMED = "RUN_RESUMED"
    RUN_BLOCKED = "RUN_BLOCKED"
    RUN_CANCELLED = "RUN_CANCELLED"
    RUN_FAILED = "RUN_FAILED"
    RUN_COMPLETED = "RUN_COMPLETED"
    PHASE_STARTED = "PHASE_STARTED"
    PHASE_COMPLETED = "PHASE_COMPLETED"
    PHASE_STATUS_CHANGED = "PHASE_STATUS_CHANGED"
    GOAL_VERSION_CREATED = "GOAL_VERSION_CREATED"
    ACCEPTANCE_CREATED = "ACCEPTANCE_CREATED"
    PLAN_CREATED = "PLAN_CREATED"
    PLAN_REVISED = "PLAN_REVISED"
    TASK_CREATED = "TASK_CREATED"
    TASK_READY = "TASK_READY"
    TASK_STARTED = "TASK_STARTED"
    TASK_WAITING = "TASK_WAITING"
    TASK_BLOCKED = "TASK_BLOCKED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    TASK_CANCELLED = "TASK_CANCELLED"
    ACTOR_STARTED = "ACTOR_STARTED"
    ACTOR_STATUS_CHANGED = "ACTOR_STATUS_CHANGED"
    ACTOR_COMPLETED = "ACTOR_COMPLETED"
    AGENT_ASSIGNED = "AGENT_ASSIGNED"
    SKILL_LOADED = "SKILL_LOADED"
    EXTERNAL_RESULT_REPORTED = "EXTERNAL_RESULT_REPORTED"
    FINDING_REPORTED = "FINDING_REPORTED"
    FINDING_RESOLVED = "FINDING_RESOLVED"
    EVIDENCE_RECORDED = "EVIDENCE_RECORDED"
    CRITERION_PASSED = "CRITERION_PASSED"
    CRITERION_FAILED = "CRITERION_FAILED"
    REVIEW_STARTED = "REVIEW_STARTED"
    REVIEW_COMPLETED = "REVIEW_COMPLETED"
    REPAIR_REQUESTED = "REPAIR_REQUESTED"
    REPAIR_STARTED = "REPAIR_STARTED"
    REPAIR_COMPLETED = "REPAIR_COMPLETED"
    CHANGE_GUARD_COMPLETED = "CHANGE_GUARD_COMPLETED"
    MEMORY_SYNC_STARTED = "MEMORY_SYNC_STARTED"
    MEMORY_SYNC_COMPLETED = "MEMORY_SYNC_COMPLETED"
    MEMORY_RETRIEVED = "MEMORY_RETRIEVED"
    MEMORY_INVALIDATED = "MEMORY_INVALIDATED"
    MEMORY_PROMOTED = "MEMORY_PROMOTED"
    CONTEXT_PACK_CREATED = "CONTEXT_PACK_CREATED"
    PROVIDER_INVOCATION_STARTED = "PROVIDER_INVOCATION_STARTED"
    PROVIDER_INVOCATION_COMPLETED = "PROVIDER_INVOCATION_COMPLETED"
    TOOL_STARTED = "TOOL_STARTED"
    TOOL_COMPLETED = "TOOL_COMPLETED"
    TEST_STARTED = "TEST_STARTED"
    TEST_COMPLETED = "TEST_COMPLETED"
    DOCUMENTATION_UPDATED = "DOCUMENTATION_UPDATED"
    FINAL_VALIDATION_COMPLETED = "FINAL_VALIDATION_COMPLETED"
    COMMIT_CREATED = "COMMIT_CREATED"
    PUSH_COMPLETED = "PUSH_COMPLETED"
    DELIVERY_BLOCKED = "DELIVERY_BLOCKED"
    POLICY_DENIED = "POLICY_DENIED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_RECORDED = "APPROVAL_RECORDED"


class EventPayload(Contract):
    git_author_name: str | None = None
    git_author_email: str | None = None
    tool_invocation_id: UUID | None = None
    review_id: UUID | None = None
    provider_execution_id: UUID | None = None
    skill_refs: tuple[str, ...] = ()
    previous_status: str | None = None
    status: str | None = None
    summary: str | None = None
    reason: str | None = None
    goal_version_id: UUID | None = None
    plan_version: int | None = None
    phase_execution_id: UUID | None = None
    criterion_id: UUID | None = None
    evidence_ids: tuple[UUID, ...] = ()
    finding_ids: tuple[UUID, ...] = ()
    task_ids: tuple[UUID, ...] = ()
    memory_ids: tuple[UUID, ...] = ()


class Event(Entity):
    project_id: UUID
    run_id: UUID
    sequence: int = Field(ge=1)
    event_type: EventType
    occurred_at: AwareDatetime
    phase: str | None = None
    task_id: UUID | None = None
    task_execution_id: UUID | None = None
    actor_session_id: UUID | None = None
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    status: str | None = None
    payload: EventPayload = Field(default_factory=EventPayload)
    trace_id: str | None = None
    idempotency_key: str


class EventDraft(Contract):
    event_type: EventType
    occurred_at: AwareDatetime
    payload: EventPayload = Field(default_factory=EventPayload)
    phase: str | None = None
    task_id: UUID | None = None
    task_execution_id: UUID | None = None
    actor_session_id: UUID | None = None
    idempotency_key: str = Field(min_length=1, max_length=255)
