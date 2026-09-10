from pathlib import Path
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from orqalis.domain.base import Contract, Entity
from orqalis.domain.capabilities import ToolName
from orqalis.domain.provider import ToolObservation


class ApprovedCommand(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    argv: tuple[str, ...] = Field(min_length=1)
    timeout_seconds: int = Field(default=60, ge=1, le=600)


class ExecutionPolicy(Contract):
    write_paths: tuple[str, ...] = Field(min_length=1)
    commands: tuple[ApprovedCommand, ...] = ()
    command_mode: Literal["docker", "trusted_local"] = "docker"
    container_image: str | None = None
    max_parallel_tasks: int = Field(default=4, ge=1, le=16)
    max_tool_calls: int = Field(default=40, ge=1, le=500)
    max_provider_turns: int = Field(default=12, ge=1, le=100)
    max_file_bytes: int = Field(default=200_000, ge=1, le=1_000_000)

    @model_validator(mode="after")
    def valid_policy(self) -> Self:
        if len({command.id for command in self.commands}) != len(self.commands):
            raise ValueError("Approved command IDs must be unique")
        if any(
            not path
            or path.startswith(("/", "\\"))
            or ".." in path.split("/")
            or "\\" in path
            or ":" in path
            for path in self.write_paths
        ):
            raise ValueError("Write scope must contain repository-relative path patterns")
        if self.commands and self.command_mode == "docker" and not self.container_image:
            raise ValueError("Docker commands require an explicitly configured image")
        return self


class RunWorkspace(Contract):
    run_id: UUID
    path: Path
    base_commit: str
    branch: str
    policy: ExecutionPolicy


class ToolInvocation(Entity):
    run_id: UUID
    task_execution_id: UUID
    actor_session_id: UUID
    provider_invocation_id: UUID
    call_id: str
    tool: ToolName
    request_hash: str
    status: Literal["RUNNING", "SUCCEEDED", "FAILED", "INTERRUPTED"] = "RUNNING"
    started_at: AwareDatetime
    completed_at: AwareDatetime | None = None
    observation: ToolObservation | None = None


class WorkerResult(Contract):
    summary: str
    completed: bool
    artifact_paths: tuple[str, ...]


class SourceCheck(Contract):
    path: str
    contains: str = Field(min_length=1)


class CriterionReview(Contract):
    criterion_id: UUID
    status: Literal["PASS", "FAIL"]
    reason: str
    evidence_refs: tuple[UUID, ...]
    source_checks: tuple[SourceCheck, ...]


class ReviewResult(Contract):
    overall: Literal["PASS", "FAIL"]
    criteria: tuple[CriterionReview, ...]
    blocking_findings: tuple[str, ...]
    non_blocking_findings: tuple[str, ...]


class ReviewRecord(Entity):
    run_id: UUID
    goal_version_id: UUID
    plan_version: int
    actor_session_id: UUID
    tree_hash: str
    result: ReviewResult


class ExecutionSummary(Contract):
    run_id: UUID
    workspace: Path
    state: str
    review: ReviewRecord | None
    completed_tasks: int
