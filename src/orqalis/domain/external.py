from pathlib import Path
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from orqalis.domain.acceptance import GoalContract
from orqalis.domain.base import Contract
from orqalis.domain.capabilities import LoadedSkill, ToolName
from orqalis.domain.memory import ContextPack
from orqalis.domain.task import Task, TaskExecution


class WorkAssignment(Contract):
    task: Task
    execution: TaskExecution
    workspace: Path
    goal: GoalContract
    context: ContextPack
    skills: tuple[LoadedSkill, ...]
    allowed_tools: tuple[ToolName, ...]


class FindingReport(Contract):
    """Untrusted worker observation; identity, ownership and resolution are server-owned."""

    severity: Literal["info", "warning", "blocking"]
    summary: str = Field(min_length=1, max_length=4000)
    criterion_id: UUID | None = None
    source_ref: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def anchored(self) -> Self:
        if not self.summary.strip():
            raise ValueError("A finding requires an actionable summary")
        if not self.criterion_id and not self.source_ref:
            raise ValueError("A finding requires a criterion or source reference")
        if self.source_ref and (
            self.source_ref.startswith(("/", "\\"))
            or ".." in self.source_ref.split("/")
            or "\\" in self.source_ref
            or ":" in self.source_ref
        ):
            raise ValueError("Finding source must be a repository-relative path")
        return self
