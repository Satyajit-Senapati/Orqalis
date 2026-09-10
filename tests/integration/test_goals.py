from pathlib import Path

import pytest
from sqlalchemy import Engine

from orqalis.core.goals import GoalService
from orqalis.core.projects import ProjectService
from orqalis.domain.acceptance import (
    AcceptanceStatus,
    CriterionDefinition,
    FileValidation,
    GoalDraft,
)
from orqalis.domain.errors import ConflictError
from orqalis.evaluation.validators import LocalEvaluator
from orqalis.git.service import LocalGitService
from orqalis.persistence.database import session_factory
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork

pytestmark = pytest.mark.postgres


def test_persisted_goals_evidence_idempotency_and_revision(
    database: Engine, git_repo: Path
) -> None:
    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    git = LocalGitService()
    project = ProjectService(factory, git).initialize(git_repo)
    draft = GoalDraft(
        goal="Validate fixture",
        scope=("main.py",),
        constraints=("retain user work",),
        definition_of_done=("Required criterion passes with evidence",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="main.py has expected content",
                validation_spec=FileValidation(path="main.py", contains="42"),
            ),
        ),
    )
    goals = GoalService(factory)
    run, original = goals.create(
        project, "Validate fixture", "feature/test", git.status(git_repo).head, draft
    )
    assert GoalService(factory).get(run.id) == original
    evidence = goals.validate(run.id, "AC-1", LocalEvaluator(git_repo), "first")
    assert evidence.structured_data.passed
    assert goals.get(run.id).criteria[0].status == AcceptanceStatus.PASS
    (git_repo / "main.py").write_text("different")
    assert goals.validate(run.id, "AC-1", LocalEvaluator(git_repo), "first") == evidence
    assert goals.get(run.id).criteria[0].attempt_count == 1
    failed = goals.validate(run.id, "AC-1", LocalEvaluator(git_repo), "second")
    assert not failed.structured_data.passed
    assert goals.get(run.id).criteria[0].status == AcceptanceStatus.FAIL
    revised = goals.revise(run.id, draft, "Explicit contract revision", expected_version=1)
    assert revised.goal.version == 2
    assert revised.goal.supersedes_goal_version_id == original.goal.id
    assert revised.criteria[0].status == AcceptanceStatus.PENDING
    assert revised.criteria[0].evidence_refs == ()
    with factory() as uow:
        previous = uow.runs.get_goal(original.goal.id)
        assert previous and previous.criteria[0].attempt_count == 2
        assert uow.runs.get_evidence(evidence.id) == evidence
    with pytest.raises(ConflictError):
        goals.revise(run.id, draft, "stale caller", expected_version=1)


def test_goal_cli(database: Engine, git_repo: Path, tmp_path: Path) -> None:
    import json

    from typer.testing import CliRunner

    from orqalis.cli.app import app

    runner = CliRunner()
    assert runner.invoke(app, ["init", "--repo", str(git_repo)]).exit_code == 0
    draft = GoalDraft(
        goal="Check file",
        scope=("main.py",),
        definition_of_done=("file exists",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="file exists",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    )
    contract = tmp_path / "goal.json"
    contract.write_text(draft.model_dump_json())
    created = runner.invoke(
        app,
        [
            "goal",
            "create",
            "Check file",
            "--contract",
            str(contract),
            "--branch",
            "feature/check",
            "--repo",
            str(git_repo),
            "--json",
        ],
    )
    assert created.exit_code == 0, created.output
    run_id = json.loads(created.stdout)["goal"]["run_id"]
    result = runner.invoke(
        app,
        [
            "goal",
            "validate",
            run_id,
            "AC-1",
            "--workspace",
            str(git_repo),
            "--idempotency-key",
            "first",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    shown = runner.invoke(app, ["goal", "show", run_id, "--json"])
    assert shown.exit_code == 0, shown.output
    assert json.loads(shown.stdout)["criteria"][0]["status"] == "PASS"
