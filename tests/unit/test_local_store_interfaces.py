import asyncio
import json
import subprocess
from pathlib import Path

import pytest
from mcp import Client
from typer.testing import CliRunner

from orqalis.cli.app import app
from orqalis.domain.project import Project
from orqalis.domain.run import Run
from orqalis.mcp.policy import MCPPolicy
from orqalis.mcp.server import create_mcp
from orqalis.persistence.filesystem.task_store import TaskCapsuleStore
from orqalis.sdk import Orqalis


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=True, text=True
    )
    return result.stdout.strip()


def repository(root: Path) -> Path:
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Orqalis Test")
    git(root, "config", "user.email", "test@orqalis.invalid")
    (root / "main.py").write_text("def tablet_navigation():\n    return True\n", encoding="utf-8")
    git(root, "add", "main.py")
    git(root, "commit", "-m", "initial")
    return root


def task_fixture(root: Path) -> tuple[Orqalis, Project, Run, str]:
    sdk = Orqalis(root=root)
    project = sdk.initialize(root)
    run = Run(
        project_id=project.id,
        request="Inspect tablet navigation",
        target_branch="feature/tablet-navigation",
        base_commit=git(root, "rev-parse", "HEAD"),
    )
    with sdk.unit_of_work() as uow:
        uow.runs.add(run)
        uow.commit()
    store = TaskCapsuleStore.from_root(root)
    task_id = store.capsule_id(run.id)
    assert task_id is not None and sdk.contexts is not None
    sdk.contexts.create(run.id)
    return sdk, project, run, task_id


def test_local_store_cli_tasks_context_graph_and_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repository(tmp_path / "repo")
    sdk, project, _, task_id = task_fixture(root)
    sdk.close()
    runner = CliRunner()

    listed = runner.invoke(app, ["tasks", "--repo", str(root), "--json"])
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.stdout)[0]["id"] == task_id
    shown = runner.invoke(app, ["task", "show", task_id, "--repo", str(root), "--json"])
    assert shown.exit_code == 0, shown.output
    assert json.loads(shown.stdout)["context"]["task"] == "Inspect tablet navigation"
    for arguments in (
        ["context", "tablet navigation", "--repo", str(root), "--json"],
        ["rebuild-index", "--repo", str(root), "--json"],
        ["memory", "graph", "--repo", str(root), "--json"],
    ):
        result = runner.invoke(app, arguments)
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)

    nested = root / "src" / "nested"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    discovered = runner.invoke(app, ["context", "tablet navigation", "--json"])
    assert discovered.exit_code == 0, discovered.output
    assert json.loads(discovered.stdout)["project_id"] == str(project.id)
    explicit_nested = runner.invoke(
        app,
        ["context", "tablet navigation", "--repo", str(nested), "--json"],
    )
    assert explicit_nested.exit_code == 0, explicit_nested.output
    assert json.loads(explicit_nested.stdout)["project_id"] == str(project.id)


def test_mcp_exposes_root_isolated_local_store_tools(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    sdk, project, _, task_id = task_fixture(root)
    policy = MCPPolicy(project_id=project.id, workspaces_root=tmp_path / "worktrees")

    async def scenario() -> None:
        async with Client(create_mcp(sdk, policy)) as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            assert {
                "get_project_context",
                "get_project_graph",
                "get_related_symbols",
                "list_tasks",
                "get_task",
                "get_task_context",
                "propose_memory_update",
                "refresh_project_memory",
            } <= names
            calls: tuple[tuple[str, dict[str, object]], ...] = (
                ("get_project_context", {"task": "tablet navigation"}),
                ("get_project_graph", {}),
                ("get_related_symbols", {"task": "tablet navigation"}),
                ("list_tasks", {}),
                ("get_task", {"task_id": task_id}),
                ("get_task_context", {"task_id": task_id}),
            )
            for name, arguments in calls:
                result = await client.call_tool(name, arguments)
                assert not result.is_error, (name, result.content)

    try:
        asyncio.run(scenario())
    finally:
        sdk.close()
