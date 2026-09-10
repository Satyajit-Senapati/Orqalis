from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator, model_validator

from orqalis.domain.base import Contract, Entity


class AcceptanceStatus(StrEnum):
    PENDING = "PENDING"
    TESTING = "TESTING"
    PASS = "PASS"
    FAIL = "FAIL"


class CommandValidation(Contract):
    kind: Literal["command", "test_suite", "static_analysis"] = "command"
    argv: tuple[str, ...] = Field(min_length=1)
    expected_exit_code: int = Field(default=0, ge=0, le=255)
    timeout_seconds: int = Field(default=60, ge=1, le=600)

    @field_validator("argv")
    @classmethod
    def valid_argv(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not part or "\x00" in part for part in value):
            raise ValueError("Command arguments must be nonempty and contain no NUL")
        return value


class FileValidation(Contract):
    kind: Literal["file"] = "file"
    path: str = Field(min_length=1)
    must_exist: bool = True
    contains: str | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if not self.must_exist and self.contains is not None:
            raise ValueError("An absent-file criterion cannot require file contents")
        return self


class DiffValidation(Contract):
    kind: Literal["diff"] = "diff"
    base_commit: str = Field(min_length=1)
    path: str = Field(min_length=1)
    contains: str = Field(min_length=1)


class ReviewValidation(Contract):
    kind: Literal["review", "manual"] = "review"
    instructions: str = Field(min_length=1)


ValidationSpec = Annotated[
    CommandValidation | FileValidation | DiffValidation | ReviewValidation,
    Field(discriminator="kind"),
]


class CriterionDefinition(Contract):
    key: str = Field(pattern=r"^AC-[A-Za-z0-9_-]+$")
    description: str = Field(min_length=1)
    priority: Literal["required", "optional"] = "required"
    validation_spec: ValidationSpec


class GoalDraft(Contract):
    goal: str = Field(min_length=1)
    scope: tuple[str, ...] = Field(min_length=1)
    out_of_scope: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    definition_of_done: tuple[str, ...] = Field(min_length=1)
    criteria: tuple[CriterionDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_required_criteria(self) -> Self:

        text = (self.goal, *self.scope, *self.definition_of_done)
        if any(not value.strip() for value in text):
            raise ValueError("Goal, scope and definition of done must be nonblank")
        keys = [criterion.key for criterion in self.criteria]
        if len(keys) != len(set(keys)):
            raise ValueError("Acceptance keys must be unique")
        if not any(criterion.priority == "required" for criterion in self.criteria):
            raise ValueError("At least one required acceptance criterion is needed")
        return self


class GoalVersion(Entity):
    run_id: UUID
    version: int = Field(ge=1)
    goal: str
    scope: tuple[str, ...]
    out_of_scope: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    definition_of_done: tuple[str, ...]
    supersedes_goal_version_id: UUID | None = None
    revision_reason: str | None = None


class AcceptanceCriterion(Entity):
    goal_version_id: UUID
    key: str
    description: str
    priority: Literal["required", "optional"]
    validation_spec: ValidationSpec
    status: AcceptanceStatus = AcceptanceStatus.PENDING
    attempt_count: int = Field(default=0, ge=0)
    last_validated_at: AwareDatetime | None = None
    evidence_refs: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def pass_requires_evidence(self) -> Self:
        if self.status == AcceptanceStatus.PASS and not self.evidence_refs:
            raise ValueError("PASS requires evidence references")
        return self


class GoalContract(Contract):
    goal: GoalVersion
    criteria: tuple[AcceptanceCriterion, ...]
