from pathlib import Path

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
