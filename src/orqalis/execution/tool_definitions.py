from pydantic import Field

from orqalis.domain.base import Contract
from orqalis.domain.capabilities import ToolName
from orqalis.domain.provider import ToolDefinition


class ReadFile(Contract):
    path: str
    start_line: int = Field(ge=1)
    line_count: int = Field(ge=1, le=300)


class WriteFile(Contract):
    path: str
    content: str = Field(max_length=200_000)


class RunCommand(Contract):
    command_id: str


class ReadDiff(Contract):
    path: str


def tool_definitions(names: tuple[ToolName, ...]) -> tuple[ToolDefinition, ...]:
    contracts: dict[ToolName, tuple[type[Contract], str]] = {
        ToolName.FILE_READ: (ReadFile, "Read bounded lines of a workspace file"),
        ToolName.FILE_WRITE: (WriteFile, "Replace an explicitly scoped file with UTF-8 text"),
        ToolName.TEST_RUN: (RunCommand, "Run a command ID from the approved policy"),
        ToolName.GIT_DIFF: (
            ReadDiff,
            "Read the diff of one workspace file against the recorded base",
        ),
    }
    return tuple(
        ToolDefinition(
            name=name,
            description=contracts[name][1],
            parameters=contracts[name][0].model_json_schema(),
        )
        for name in names
        if name in contracts
    )
