from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, Field, JsonValue, model_validator

from orqalis.domain.acceptance import GoalContract
from orqalis.domain.agent import AgentRole
from orqalis.domain.artifact import Evidence
from orqalis.domain.base import Contract, Entity
from orqalis.domain.capabilities import LoadedSkill, ToolName
from orqalis.domain.memory import ContextPack
from orqalis.domain.task import Task


class ExecutionBudget(Contract):
    timeout_seconds: float = Field(default=120, gt=0, le=3600, allow_inf_nan=False)
    max_output_tokens: int = Field(default=4096, ge=16, le=100_000)
    max_input_chars: int = Field(default=150_000, ge=100, le=2_000_000)


class ProviderDescriptor(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    model: str = Field(min_length=1, max_length=255)
    capabilities: tuple[str, ...] = ("structured_output",)
    available: bool = True
    max_input_chars: int = Field(default=150_000, gt=0)


class ToolDefinition(Contract):
    name: ToolName
    description: str
    parameters: dict[str, JsonValue]


class ProviderToolCall(Contract):
    id: str = Field(min_length=1, max_length=255)
    name: ToolName
    arguments: dict[str, JsonValue]


class ToolObservation(Contract):
    call_id: str
    tool: ToolName
    succeeded: bool
    summary: str = Field(max_length=16_000)
    evidence_ids: tuple[UUID, ...] = ()


class ProviderExecutionRequest(Contract):
    invocation_id: UUID
    run_id: UUID
    actor_session_id: UUID
    task_execution_id: UUID
    role: AgentRole
    task: Task
    context: ContextPack
    selected_skills: tuple[LoadedSkill, ...] = ()
    allowed_tools: tuple[ToolDefinition, ...] = ()
    constraints: tuple[str, ...] = ()
    observations: tuple[ToolObservation, ...] = ()
    acceptance: GoalContract | None = None
    evidence: tuple[Evidence, ...] = ()
    output_schema: dict[str, JsonValue]
    budget: ExecutionBudget = Field(default_factory=ExecutionBudget)
    trace_id: str | None = None

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.task.run_id != self.run_id or self.role != self.task.preferred_role:
            raise ValueError("Task and role must belong to this execution")
        names = [tool.name for tool in self.allowed_tools]
        if len(names) != len(set(names)):
            raise ValueError("Tool definitions must be unique")
        return self


class ProviderUsage(Contract):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    cost_source: str | None = None

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.estimated_cost_usd is not None and not self.cost_source:
            raise ValueError("Cost requires a source")
        if (
            self.cached_input_tokens is not None
            and self.input_tokens is not None
            and self.cached_input_tokens > self.input_tokens
        ):
            raise ValueError("Cached tokens cannot exceed input tokens")
        return self


class ProviderExecutionResult(Contract):
    output: dict[str, JsonValue] | None = None
    tool_calls: tuple[ProviderToolCall, ...] = ()
    usage: ProviderUsage = Field(default_factory=ProviderUsage)

    @model_validator(mode="after")
    def one_result(self) -> Self:
        if (self.output is None) == (not self.tool_calls):
            raise ValueError("Exactly one of output or tool calls is required")
        if len({call.id for call in self.tool_calls}) != len(self.tool_calls):
            raise ValueError("Tool call IDs must be unique")
        return self


class ProviderErrorCode(StrEnum):
    UNAVAILABLE = "unavailable"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    INVALID_OUTPUT = "invalid_output"
    REFUSED = "refused"
    BUDGET = "budget"
    TRANSPORT = "transport"
    INTERRUPTED = "interrupted"
    INTERNAL = "internal"


class InvocationStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


class ProviderExecution(Entity):
    run_id: UUID
    task_execution_id: UUID
    actor_session_id: UUID
    provider: str
    model: str
    request_hash: str
    idempotency_key: str
    status: InvocationStatus = InvocationStatus.RUNNING
    started_at: AwareDatetime
    deadline_at: AwareDatetime
    completed_at: AwareDatetime | None = None
    result: ProviderExecutionResult | None = None
    error_code: ProviderErrorCode | None = None
