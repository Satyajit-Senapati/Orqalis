import asyncio
import json
from pathlib import Path

from mcp import Client
from typer.testing import CliRunner

from orqalis.cli.app import app
from orqalis.context.agent import agent_context
from orqalis.mcp.policy import MCPPolicy
from orqalis.mcp.server import create_mcp
from orqalis.memory.curated import (
    CuratedMemoryStore,
    MemoryCategory,
    MemoryFreshness,
    MemoryProvenance,
)
from orqalis.persistence.filesystem.layout import ProjectLayout
from tests.unit.test_local_store_interfaces import repository, task_fixture


def test_operator_review_cli_and_progressive_mcp_keep_review_boundary(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    sdk, project, run, task_id = task_fixture(root)
    store = CuratedMemoryStore(ProjectLayout(root))
    old = store.new_record(
        MemoryCategory.DECISION,
        "Tablet durability",
        "Preserve tablet state.",
        MemoryProvenance(type="user"),
    )
    store.save(old)
    new = store.new_record(
        MemoryCategory.DECISION,
        "Tablet durability",
        "Tablet durability details. " * 2000,
        MemoryProvenance(type="user"),
        summary="Atomic tablet state.",
        references=(old.id,),
    )
    proposal = store.propose(new, "Accepted new snapshot protocol", supersedes=old.id)
    runner = CliRunner()
    args = ["--repo", str(root)]
    inspected = runner.invoke(app, ["memory", "proposal", proposal.id, *args])
    assert inspected.exit_code == 0, inspected.output
    assert json.loads(inspected.stdout)["record"]["supersedes"] == old.id
    approved = runner.invoke(
        app, ["memory", "approve", proposal.id, "--reason", "Reviewed evidence", *args]
    )
    assert approved.exit_code == 0, approved.output
    assert [item.record.id for item in sdk.search_project_memory("tablet")] == [new.id]
    assert sdk.contexts is not None
    pack = sdk.contexts.create(run.id, "tablet durability", 4000)
    assert [item.id for item in pack.memory_discovery] == [new.id]
    provider = agent_context(project, pack)
    assert any(
        "body not loaded" in item.item.content and new.id in item.item.content
        for item in provider.items
    )
    stale_pack = pack.model_copy(
        update={
            "memory_discovery": tuple(
                item.model_copy(update={"freshness": MemoryFreshness.STALE})
                for item in pack.memory_discovery
            )
        }
    )
    stale_provider = agent_context(project, stale_pack)
    assert not stale_provider.freshness.fresh
    assert stale_provider.requires_inspection
    projection = json.loads(
        (root / ".orqalis" / "tasks" / task_id / "context" / "memory-used.yaml").read_text()
    )
    assert projection["memory_discovery"][0]["id"] == new.id
    assert projection["memory_discovery"][0]["body_loaded"] is False
    for command in (["discover", "tablet"], ["get", new.id], ["check"], ["proposals"]):
        result = runner.invoke(app, ["memory", *command, *args])
        assert result.exit_code == 0, result.output

    async def scenario() -> None:
        policy = MCPPolicy(project_id=project.id, workspaces_root=tmp_path / "worktrees")
        async with Client(create_mcp(sdk, policy)) as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            assert {
                "discover_project_memory",
                "get_project_memory",
                "check_project_memory",
            } <= names
            assert not any("approve" in name and "memory" in name for name in names)
            for name, arguments in (
                ("discover_project_memory", {"query": "tablet", "max_chars": 1000}),
                ("get_project_memory", {"record_id": new.id, "max_chars": 1000}),
                ("check_project_memory", {}),
            ):
                result = await client.call_tool(name, arguments)
                assert not result.is_error, (name, result.content)
            rejected = await client.call_tool("get_project_memory", {"record_id": "../outside"})
            assert rejected.is_error

    try:
        asyncio.run(scenario())
    finally:
        sdk.close()
