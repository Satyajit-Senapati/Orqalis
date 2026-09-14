import json

from typer.testing import CliRunner

from orqalis.cli.app import app


def test_cli_lists_run_modes_and_default_gates() -> None:
    result = CliRunner().invoke(app, ["modes", "--json"])
    assert result.exit_code == 0, result.output
    modes = json.loads(result.output)
    assert modes["autonomous"]["gates"] == []
    assert modes["supervised"]["gates"] == ["GOAL", "PLAN", "REPAIR", "DELIVERY"]
