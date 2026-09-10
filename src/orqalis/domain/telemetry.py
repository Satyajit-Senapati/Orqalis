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
