import ast
import io
import json
import logging
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from orqalis import __version__
from orqalis.cli.app import app
from orqalis.config.settings import Settings
from orqalis.domain.project import Project
from orqalis.domain.task import Task
from orqalis.observability.logging import TraceContext, configure_logging, trace_context


def test_domain_is_immutable_and_rejects_unknown_fields(tmp_path: Path) -> None:
    project = Project(name="fixture", repo_root=tmp_path, default_branch="main")
    assert project.created_at.utcoffset() is not None
    assert Project.model_validate_json(project.model_dump_json()) == project
    with pytest.raises(ValidationError):
        project.name = "mutated"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        Project.model_validate({**project.model_dump(), "untrusted": True})


@pytest.mark.parametrize("weight", [0, -1, float("inf"), float("nan")])
def test_plan_weights_must_be_positive_finite(weight: float) -> None:
    with pytest.raises(ValidationError):
        Task(
            run_id=uuid4(),
            description="Task",
            expected_outcome="Result",
            validation_method="test",
            work_weight=weight,
        )


def test_settings_override_and_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORQALIS_PORT", "7890")
    monkeypatch.setenv("ORQALIS_DATABASE_URL", "postgresql+psycopg://u:private@localhost/db")
    settings = Settings()
    assert settings.port == 7890
    assert "private" not in repr(settings)
    assert "private" not in settings.model_dump_json()
    monkeypatch.setenv("ORQALIS_DATABASE_URL", "sqlite:///prototype.db")
    with pytest.raises(ValidationError):
        Settings()


def test_logging_redaction_context_and_allowlist() -> None:
    stream = io.StringIO()
    configure_logging(stream=stream)
    run_id = uuid4()
    logger = logging.getLogger("orqalis.test")
    with trace_context(TraceContext(run_id=run_id, trace_id="trace")):
        logger.info("token=secret-value", extra={"chain_of_thought": "private scratch"})
    logger.info("outside context")
    rows = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert rows[0]["run_id"] == str(run_id)
    assert rows[1]["run_id"] is None
    assert "secret-value" not in stream.getvalue()
    assert "private scratch" not in stream.getvalue()


def test_cli_help_and_version() -> None:
    runner = CliRunner()
    assert runner.invoke(app, ["--help"]).exit_code == 0
    assert runner.invoke(app, ["version"]).stdout.strip() == __version__


def test_domain_dependency_boundary() -> None:
    domain = Path(__file__).parents[2] / "src" / "orqalis" / "domain"
    forbidden = {"fastapi", "typer", "sqlalchemy", "alembic", "openai", "anthropic", "mcp"}
    for path in domain.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            assert not any(module.split(".")[0] in forbidden for module in modules), path
            assert not any(
                module.startswith(("orqalis.persistence", "orqalis.providers", "orqalis.cli"))
                for module in modules
            ), path


@pytest.mark.parametrize(
    "payload",
    [
        '{"api_key": "sensitive-test-value"}',
        "password='sensitive-test-value'",
        "ssh://user:sensitive-test-value@example.invalid",
        "-----BEGIN EC PRIVATE KEY----- sensitive-test-value",
    ],
)
def test_structured_and_key_diagnostics_are_redacted(payload: str) -> None:
    from orqalis.security.redaction import safe_diagnostic

    assert "sensitive-test-value" not in safe_diagnostic(payload)


def test_invalid_cli_configuration_does_not_echo_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORQALIS_PORT", "private-config-value")
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 2
    assert "private-config-value" not in result.output
    assert "Invalid Orqalis configuration" in result.output
