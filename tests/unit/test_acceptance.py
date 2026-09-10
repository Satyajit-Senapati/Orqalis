import sys
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from orqalis.domain.acceptance import (
    AcceptanceCriterion,
    CommandValidation,
    CriterionDefinition,
    FileValidation,
    GoalDraft,
    ReviewValidation,
)
from orqalis.domain.errors import PolicyDeniedError
from orqalis.evaluation.validators import LocalEvaluator


def draft() -> GoalDraft:
    return GoalDraft(
        goal="Add behavior",
        scope=("main.py",),
        definition_of_done=("tests pass",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="File exists",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    )


def test_invalid_contract_and_asserted_pass_rejected() -> None:
    original = draft()
    with pytest.raises(ValidationError):
        GoalDraft.model_validate({**original.model_dump(), "criteria": []})
    with pytest.raises(ValidationError):
        GoalDraft.model_validate({**original.model_dump(), "criteria": original.criteria * 2})
    with pytest.raises(ValidationError):
        AcceptanceCriterion(
            goal_version_id=uuid4(),
            key="AC-1",
            description="pass",
            priority="required",
            validation_spec=FileValidation(path="main.py"),
            status="PASS",
        )
    with pytest.raises(ValidationError):
        CommandValidation(argv=())
    with pytest.raises(ValidationError):
        FileValidation(path="main.py", must_exist=False, contains="text")


def test_file_validators(tmp_path: Path) -> None:
    evaluator = LocalEvaluator(tmp_path)
    assert not evaluator.evaluate(FileValidation(path="main.py")).passed
    (tmp_path / "main.py").write_text("def example(): pass")
    observation = evaluator.evaluate(FileValidation(path="main.py", contains="example"))
    assert observation.passed and observation.content_hash
    assert not evaluator.evaluate(FileValidation(path="main.py", contains="missing")).passed
    with pytest.raises(PolicyDeniedError):
        evaluator.evaluate(FileValidation(path="../outside"))


def test_command_failures_not_swallowed_and_commands_require_opt_in(tmp_path: Path) -> None:
    argv = (sys.executable, "-c", "import sys; print('token=private-value'); sys.exit(7)")
    spec = CommandValidation(argv=argv)
    with pytest.raises(PolicyDeniedError):
        LocalEvaluator(tmp_path).evaluate(spec)
    result = LocalEvaluator(tmp_path, frozenset({argv})).evaluate(spec)
    assert not result.passed and result.exit_code == 7
    assert "private-value" not in result.output
    assert result.duration_ms >= 0


def test_timeout_and_review_are_not_passes(tmp_path: Path) -> None:
    argv = (sys.executable, "-c", "import time; time.sleep(5)")
    result = LocalEvaluator(tmp_path, frozenset({argv})).evaluate(
        CommandValidation(argv=argv, timeout_seconds=1)
    )
    assert not result.passed and result.error_code == "timeout"
    assert (
        not LocalEvaluator(tmp_path).evaluate(ReviewValidation(instructions="Review scope")).passed
    )


def test_diff_assertion_and_private_diagnostics(git_repo: Path) -> None:
    from orqalis.domain.acceptance import DiffValidation

    (git_repo / "main.py").write_text("answer = 43")
    result = LocalEvaluator(git_repo).evaluate(
        DiffValidation(base_commit="HEAD", path="main.py", contains="+answer = 43")
    )
    assert result.passed and result.content_hash
    argv = (sys.executable, "-c", "print('<thinking>private scratch</thinking>')")
    observed = LocalEvaluator(git_repo, frozenset({argv})).evaluate(CommandValidation(argv=argv))
    assert observed.passed
    assert "private scratch" not in observed.output
