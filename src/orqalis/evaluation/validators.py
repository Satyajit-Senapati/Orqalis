import hashlib
from pathlib import Path
from time import monotonic_ns

from orqalis.domain.acceptance import (
    CommandValidation,
    DiffValidation,
    FileValidation,
    ValidationSpec,
)
from orqalis.domain.artifact import ValidationObservation
from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.execution import ApprovedCommand, ExecutionPolicy
from orqalis.execution.commands import CommandRunner
from orqalis.execution.filesystem import ScopedFilesystem
from orqalis.git.service import LocalGitService


class LocalEvaluator:
    """Trusted-local validators with an exact command allowlist.

    Worker commands use WorkspaceEvaluator with the approved Docker policy.
    Repository/model-proposed argv are denied unless explicitly configured by the caller.
    """

    def __init__(
        self, workspace: Path, allowed_commands: frozenset[tuple[str, ...]] = frozenset()
    ) -> None:
        self.workspace = workspace.resolve(strict=True)
        self.allowed_commands = allowed_commands

    def evaluate(self, spec: ValidationSpec) -> ValidationObservation:
        started = monotonic_ns()
        if isinstance(spec, CommandValidation):
            return self._command(spec, started)

        if isinstance(spec, DiffValidation):
            diff = LocalGitService().diff_text(self.workspace, spec.base_commit, spec.path)
            return ValidationObservation(
                validator_type="diff",
                passed=spec.contains in diff.decode("utf-8", errors="replace"),
                source_ref=spec.path,
                content_hash=hashlib.sha256(diff).hexdigest(),
                duration_ms=(monotonic_ns() - started) // 1_000_000,
            )
        if isinstance(spec, FileValidation):
            return self._file(spec, started)
        return ValidationObservation(
            validator_type=spec.kind,
            passed=False,
            error_code="review_evidence_required",
            duration_ms=0,
        )

    def _command(self, spec: CommandValidation, started: int) -> ValidationObservation:
        if spec.argv not in self.allowed_commands:
            raise PolicyDeniedError("Validation command is not explicitly allowed")
        command = ApprovedCommand(
            id="criterion-check", argv=spec.argv, timeout_seconds=spec.timeout_seconds
        )
        policy = ExecutionPolicy(
            write_paths=("*",), commands=(command,), command_mode="trusted_local"
        )
        return CommandRunner(self.workspace, policy).run(
            command, spec.kind, spec.expected_exit_code
        )

    def _file(self, spec: FileValidation, started: int) -> ValidationObservation:
        target = ScopedFilesystem(
            self.workspace, ExecutionPolicy(write_paths=("*",), max_file_bytes=1_000_000)
        ).target(spec.path)
        exists = target.is_file()
        passed = exists == spec.must_exist
        content_hash = None
        error = None
        if passed and spec.contains is not None:
            try:
                if target.stat().st_size > 1_000_000:
                    passed, error = False, "file_too_large"
                else:
                    with target.open("rb") as stream:
                        content = stream.read(1_000_001)
                    if len(content) > 1_000_000:
                        raise OSError("File exceeded the validation limit")
                    content_hash = hashlib.sha256(content).hexdigest()
                    passed = spec.contains in content.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                passed, error = False, "file_unreadable"
        return ValidationObservation(
            validator_type=spec.kind,
            passed=passed,
            source_ref=spec.path,
            content_hash=content_hash,
            error_code=error,
            duration_ms=(monotonic_ns() - started) // 1_000_000,
        )
