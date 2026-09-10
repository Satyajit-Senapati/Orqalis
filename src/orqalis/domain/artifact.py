from typing import Literal
from uuid import UUID

from pydantic import Field

from orqalis.domain.base import Contract, Entity


class ValidationObservation(Contract):
    validator_type: str
    passed: bool
    exit_code: int | None = None
    output: str = ""
    source_ref: str | None = None
    content_hash: str | None = None
    error_code: str | None = None
    duration_ms: int = Field(ge=0)


class Evidence(Entity):
    run_id: UUID
    criterion_id: UUID
    task_id: UUID | None = None
    task_execution_id: UUID | None = None
    evidence_type: str
    artifact_ref: UUID | None = None
    structured_data: ValidationObservation
    status: Literal["valid", "invalid"] = "valid"


class Artifact(Entity):
    run_id: UUID
    task_id: UUID | None = None
    type: str
    path_or_uri: str
    content_hash: str


class Finding(Entity):
    run_id: UUID
    task_id: UUID | None = None
    criterion_id: UUID | None = None
    severity: Literal["info", "warning", "blocking"]
    category: str
    summary: str
    source_ref: str | None = None
    status: Literal["open", "resolved"] = "open"
