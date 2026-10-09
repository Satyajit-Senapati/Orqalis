from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from orqalis.domain.base import Contract
from orqalis.domain.provider import ProviderUsage


class TimelineSegment(Contract):
    kind: Literal["actor", "task", "phase"]
    entity_id: UUID
    task_id: UUID | None = None
    status: str
    started_at: AwareDatetime
    ended_at: AwareDatetime
    duration_ms: int = Field(ge=0)


class TraceNode(Contract):
    """Rebuildable local operation hierarchy; IDs never imply a hosted trace export."""

    id: str
    entity_id: UUID
    kind: Literal["run", "phase", "task", "actor", "model", "tool"]
    parent_id: str | None = None
    related_ids: tuple[str, ...] = ()
    label: str
    status: str
    started_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    task_id: UUID | None = None
    task_execution_id: UUID | None = None
    actor_session_id: UUID | None = None
    provider_invocation_id: UUID | None = None


class ProviderCallProjection(Contract):
    id: UUID
    actor_session_id: UUID
    task_execution_id: UUID
    provider: str
    model: str
    status: str
    started_at: AwareDatetime
    completed_at: AwareDatetime | None
    error_code: str | None
    usage: ProviderUsage | None
    selected_skills: tuple[str, ...] = ()
    context_memory_ids: tuple[UUID, ...] = ()
    context_summary: str | None = None


class ProviderStatistics(Contract):
    provider: str
    model: str
    calls: int
    succeeded: int
    failed: int
    cancelled: int
    interrupted: int
    running: int
    calls_with_latency: int
    p50_latency_ms: int | None = None
    p95_latency_ms: int | None = None
    calls_with_usage: int
    calls_with_cost: int
    reported_input_tokens: int | None = None
    reported_output_tokens: int | None = None
    reported_cost_usd: float | None = None
    errors: dict[str, int] = Field(default_factory=dict)


class RuntimeStatistics(Contract):
    max_parallel_tasks: int = 0
    mean_parallel_tasks: float = 0
    critical_path_task_ids: tuple[UUID, ...] = ()
    critical_path_working_ms: int = 0
    provider_calls: int = 0
    tool_calls: int = 0
    calls_with_usage: int = 0
    reported_input_tokens: int | None = None
    reported_output_tokens: int | None = None
    reported_cached_tokens: int | None = None
    reported_cost_usd: float | None = None
    calls_with_cost: int = 0
    first_pass_success: bool | None = None
    providers: tuple[ProviderStatistics, ...] = ()


class SkillActivity(Contract):
    ref: str
    load_count: int
    actor_session_ids: tuple[UUID, ...]
    last_loaded_at: AwareDatetime
