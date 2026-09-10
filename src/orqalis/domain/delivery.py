from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from orqalis.domain.artifact import Finding
from orqalis.domain.base import Contract, Entity


class DeliveryPolicy(Contract):
    documentation_path: str | None = None
    approved_sensitive_paths: tuple[str, ...] = ()
    max_deleted_line_ratio: float = Field(default=0.5, ge=0, le=1)
    push: bool = False
    remote: str = Field(default="origin", pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    allow_local_remote: bool = False
    author_name: str | None = None
    author_email: str | None = None

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if bool(self.author_name) != bool(self.author_email):
            raise ValueError("Commit author name and email must be supplied together")
        return self


class ChangedFile(Contract):
    path: str
    status: Literal["added", "modified", "deleted"]
    old_hash: str | None
    new_hash: str | None
    added_lines: int = Field(ge=0)
    deleted_lines: int = Field(ge=0)
    binary: bool


class ChangeReport(Entity):
    run_id: UUID
    actor_session_id: UUID
    checkpoint: Literal["implementation", "final"]
    base_commit: str
    tree_hash: str
    passed: bool
    changes: tuple[ChangedFile, ...]
    findings: tuple[Finding, ...]


class FinalValidation(Entity):
    run_id: UUID
    actor_session_id: UUID
    goal_version_id: UUID
    tree_hash: str
    passed: bool
    evidence_ids: tuple[UUID, ...]


class GitDelivery(Entity):
    run_id: UUID
    base_commit: str
    branch: str
    tree_hash: str
    git_tree_sha: str
    commit_message: str
    commit_attached: bool = False
    commit_sha: str | None = None
    push_status: Literal["not_requested", "pending", "pushed"] = "not_requested"
    remote: str | None = None
    policy: DeliveryPolicy


class DeliveryResult(Contract):
    run_id: UUID
    state: str
    commit_sha: str | None
    pushed: bool
    changed_paths: tuple[str, ...]
