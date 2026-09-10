from enum import StrEnum

from pydantic import Field

from orqalis.domain.agent import AgentRole
from orqalis.domain.base import Contract


class ToolName(StrEnum):
    FILE_READ = "filesystem.read"
    FILE_WRITE = "filesystem.write"
    SHELL_RUN = "shell.run"
    TEST_RUN = "test.run"
    GIT_DIFF = "git.diff"
    MEMORY_QUERY = "memory.query"


class PermissionProfile(Contract):
    allowed_tools: tuple[ToolName, ...] = ()
    network_allowed: bool = False


class RoleDefinition(Contract):
    role: AgentRole
    responsibility: str
    permissions: PermissionProfile
    capabilities: tuple[str, ...]
    can_approve_acceptance: bool = False


class SkillMetadata(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    description: str = Field(min_length=1, max_length=2000)
    capabilities: tuple[str, ...] = Field(min_length=1)
    applicable_when: tuple[str, ...] = ()
    required_tools: tuple[ToolName, ...] = ()
    constraints: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()


class LoadedSkill(Contract):
    metadata: SkillMetadata
    instructions: str = Field(max_length=100_000)
    content_hash: str
