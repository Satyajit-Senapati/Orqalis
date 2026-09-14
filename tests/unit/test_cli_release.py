"""Release-facing CLI checks require no database or provider credentials."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from orqalis import __version__
from orqalis.cli.app import app
from orqalis.domain.agent import AgentRole


def test_version_flag_works_without_valid_runtime_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ORQALIS_PORT", "invalid-private-setting")
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == __version__
    assert result.stderr == ""


def test_cli_catalogs_work_without_database() -> None:
    runner = CliRunner()
    roles = runner.invoke(app, ["agents", "--json"])
    assert roles.exit_code == 0, roles.output
    records = json.loads(roles.stdout)
    assert {entry["role"] for entry in records} == set(AgentRole)
    reviewer = next(entry for entry in records if entry["role"] == "reviewer")
    assert reviewer["can_approve_acceptance"] is True
    assert "filesystem.write" not in reviewer["permissions"]["allowed_tools"]
    catalog = runner.invoke(app, ["skills", "--json"])
    assert catalog.exit_code == 0, catalog.output
    skills = json.loads(catalog.stdout)
    assert {item["id"] for item in skills} >= {"python-edit", "python-test", "evidence-review"}
    assert all("instructions" not in skill for skill in skills)
    assert runner.invoke(app, ["agents"]).exit_code == 0
    assert runner.invoke(app, ["skills"]).exit_code == 0


def test_cli_config_show_never_reveals_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "ORQALIS_DATABASE_URL", "postgresql+psycopg://private-user:private-password@localhost/db"
    )
    monkeypatch.setenv("ORQALIS_OPENAI_API_KEY", "private-openai-value")
    monkeypatch.setenv("ORQALIS_ANTHROPIC_API_KEY", "private-anthropic-value")
    monkeypatch.setenv("ORQALIS_PORT", "7850")
    for arguments in (["config", "show", "--json"], ["config", "show"]):
        result = CliRunner().invoke(app, arguments)
        assert result.exit_code == 0, result.output
        assert "private-" not in result.output
        assert "postgresql+psycopg://" not in result.output
    values = json.loads(CliRunner().invoke(app, ["config", "show", "--json"]).stdout)
    assert values["port"] == 7850
    assert values["openai_api_key_configured"] is True
    assert values["anthropic_api_key_configured"] is True


@pytest.mark.parametrize("command", ["capabilities", "skills"])
def test_cli_missing_skill_root_has_readable_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, command: str
) -> None:
    monkeypatch.setenv("ORQALIS_SKILL_ROOTS", json.dumps([str(tmp_path / "missing")]))
    result = CliRunner().invoke(app, [command])
    assert result.exit_code == 1
    assert "filesystem_error" in result.stderr
    assert "Traceback" not in result.output
    assert str(tmp_path) not in result.output


@pytest.mark.parametrize("command", ["capabilities", "skills"])
def test_cli_rejects_private_skill_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, command: str
) -> None:
    skill = tmp_path / "unsafe"
    skill.mkdir()
    (skill / "skill.toml").write_text(
        'id = "unsafe"\nversion = "1.0.0"\n'
        'description = "password=private-skill-value"\ncapabilities = ["unsafe"]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("ORQALIS_SKILL_ROOTS", json.dumps([str(tmp_path)]))
    result = CliRunner().invoke(app, [command])
    assert result.exit_code == 1
    assert "policy_denied" in result.stderr
    assert "private-skill-value" not in result.output


@pytest.mark.parametrize(
    "arguments", [["missing-command"], ["status", "--invalid"], ["runs", "show", "not-a-uuid"]]
)
def test_cli_invalid_input_has_usage_exit_code(arguments: list[str]) -> None:
    result = CliRunner().invoke(app, arguments)
    assert result.exit_code == 2
    assert "Traceback" not in result.output


def test_cli_serve_denies_remote_binding_without_traceback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORQALIS_HOST", "0.0.0.0")
    result = CliRunner().invoke(app, ["serve"])
    assert result.exit_code == 1
    assert "policy_denied" in result.stderr
    assert "Traceback" not in result.output


def test_update_is_discoverable_but_requires_npm_launcher() -> None:
    runner = CliRunner()
    help_result = runner.invoke(app, ["--help"])
    assert help_result.exit_code == 0
    assert "update" in help_result.stdout

    source_result = runner.invoke(app, ["update"])
    assert source_result.exit_code == 2
    assert "globally installed npm launcher" in source_result.output


@pytest.mark.parametrize("owned", [True, False])
def test_ui_command_waits_only_for_its_terminal_owned_host(
    monkeypatch: pytest.MonkeyPatch, owned: bool
) -> None:
    cli = import_module("orqalis.cli.app")
    events: list[str] = []

    class Host:
        url = "http://127.0.0.1:7842"

        def __init__(self) -> None:
            self.owned = owned

        def wait(self) -> None:
            events.append("wait")

    @contextmanager
    def session(settings: object, open_path: str | None = None) -> Iterator[Host]:
        assert open_path == "/"
        events.append("enter")
        try:
            yield Host()
        finally:
            events.append("close")

    monkeypatch.setattr(cli, "ui_session", session)
    result = CliRunner().invoke(app, ["ui", "--open"])
    assert result.exit_code == 0, result.output
    assert "http://127.0.0.1:7842" in result.stdout
    assert events == (["enter", "wait", "close"] if owned else ["enter", "close"])


def test_run_open_keeps_ui_during_goal_and_closes_owned_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cli = import_module("orqalis.cli.app")
    events: list[str] = []
    run_id = uuid4()
    project = SimpleNamespace(id=uuid4())
    projects = SimpleNamespace(status=lambda repo: (project, object()), unit_of_work=object())

    @contextmanager
    def project_service() -> Iterator[SimpleNamespace]:
        try:
            yield projects
        finally:
            events.append("project_close")

    @contextmanager
    def session(settings: object, open_path: str | None = None) -> Iterator[SimpleNamespace]:
        assert open_path == f"/runs/{run_id}"
        events.append("ui_enter")
        try:
            yield SimpleNamespace(
                owned=True,
                wait=lambda: events.append("ui_wait"),
            )
        finally:
            events.append("ui_close")

    class FakeOrqalis:
        def __init__(self, unit_of_work: object) -> None:
            pass

        def prepare_run(self, *args: object) -> SimpleNamespace:
            events.append("goal_prepared")
            return SimpleNamespace(run=SimpleNamespace(id=run_id, state="GOAL_DEFINED"))

    monkeypatch.setattr(cli, "project_service", project_service)
    monkeypatch.setattr(cli, "ui_session", session)
    monkeypatch.setattr(cli, "Orqalis", FakeOrqalis)
    contract = Path(__file__).parents[2] / "docs/examples/goal.json"
    result = CliRunner().invoke(
        app,
        ["run", "Inspect fixture", "--repo", str(tmp_path), "--contract", str(contract), "--open"],
    )
    assert result.exit_code == 0, result.output
    assert str(run_id) in result.stdout
    assert events == ["goal_prepared", "ui_enter", "ui_wait", "ui_close", "project_close"]
