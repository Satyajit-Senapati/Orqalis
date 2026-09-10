from pathlib import Path

from pydantic import AwareDatetime, Field

from orqalis.domain.base import Contract, Entity, utc_now
from orqalis.domain.capabilities import PermissionProfile, ToolName


class RepositoryProfile(Contract):
    languages: tuple[str, ...] = ()
    build_manifests: tuple[str, ...] = ()
    test_paths: tuple[str, ...] = ()
    instruction_paths: tuple[str, ...] = ()


class ProjectSettings(Contract):
    permissions: PermissionProfile = Field(
        default_factory=lambda: PermissionProfile(
            allowed_tools=(
                ToolName.FILE_READ,
                ToolName.FILE_WRITE,
                ToolName.TEST_RUN,
                ToolName.GIT_DIFF,
                ToolName.MEMORY_QUERY,
            )
        )
    )
    allowed_providers: tuple[str, ...] = ()
    skill_pins: dict[str, str] = Field(default_factory=dict)
    repository_profile: RepositoryProfile = Field(default_factory=RepositoryProfile)
    protected_branches: tuple[str, ...] = ("main", "master")
    allow_push: bool = False
    max_task_attempts: int = Field(default=3, ge=1, le=20)
    max_repair_iterations: int = Field(default=5, ge=0, le=100)


class Project(Entity):
    name: str = Field(min_length=1)
    repo_uri: str | None = None
    repo_root: Path
    default_branch: str = Field(min_length=1)
    settings: ProjectSettings = Field(default_factory=ProjectSettings)
    updated_at: AwareDatetime = Field(default_factory=utc_now)
