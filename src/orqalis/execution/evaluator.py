from pathlib import Path

from orqalis.domain.acceptance import CommandValidation, ValidationSpec
from orqalis.domain.artifact import ValidationObservation
from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.execution import ExecutionPolicy
from orqalis.evaluation.validators import LocalEvaluator
from orqalis.execution.commands import CommandRunner


class WorkspaceEvaluator:
    def __init__(self, workspace: Path, policy: ExecutionPolicy) -> None:
        self.local = LocalEvaluator(workspace)
        self.commands = CommandRunner(workspace, policy)
        self.policy = policy

    def evaluate(self, spec: ValidationSpec) -> ValidationObservation:
        if isinstance(spec, CommandValidation):
            command = next((item for item in self.policy.commands if item.argv == spec.argv), None)
            if command is None or command.timeout_seconds > spec.timeout_seconds:
                raise PolicyDeniedError("Criterion command exceeds the approved policy")
            return self.commands.run(command, spec.kind, spec.expected_exit_code)
        return self.local.evaluate(spec)
