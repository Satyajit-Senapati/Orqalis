"""Direct MCP factories must enforce policy even without CLI startup validation."""

import asyncio
from pathlib import Path

from mcp import Client

from orqalis.config.settings import Settings
from orqalis.mcp.policy import MCPPolicy
from orqalis.mcp.server import create_mcp
from orqalis.memory.curated import CuratedMemoryStore, MemoryCategory, MemoryProvenance
from orqalis.persistence.filesystem import ProjectLayout
from orqalis.sdk import Orqalis
from tests.conftest import fixture_git
from tests.unit.test_portable_skills import skill


def test_direct_factory_denies_other_project_memory_and_configured_skills(
    git_repo: Path, tmp_path: Path
) -> None:
    other = tmp_path / "other-project"
    other.mkdir()
    fixture_git(other, "init", "-b", "main")
    (other / "main.py").write_text("answer = 43\n", encoding="utf-8")
    fixture_git(other, "add", ".")
    fixture_git(other, "commit", "-m", "other project")
    skills = git_repo / "local-skills"
    skills.mkdir()
    directory = skill(skills, 'metadata:\n  orqalis-version: "1.2.0"\n')
    (directory / "references").mkdir()
    (directory / "references/guide.md").write_text("Project A guidance.", encoding="utf-8")
    sdk = Orqalis(root=git_repo, settings=Settings(skill_roots=(skills,)))
    other_sdk = Orqalis(root=other)
    project = sdk.initialize(git_repo)
    other_project = other_sdk.initialize(other)
    store = CuratedMemoryStore(ProjectLayout(git_repo))
    decision = store.new_record(
        MemoryCategory.DECISION,
        "Project A private decision",
        "Keep the project A decision within its authorized project.",
        MemoryProvenance(type="user"),
    )
    store.save(decision)
    policy = MCPPolicy(project_id=project.id, workspaces_root=tmp_path / "workers")
    wrong_policy = policy.model_copy(update={"project_id": other_project.id})
    skill_args: dict[str, object] = {"skill_id": "code-review", "version": "1.2.0"}
    guarded_calls: tuple[tuple[str, dict[str, object]], ...] = (
        ("get_decisions", {"topic": "Project A"}),
        ("search_project_memory", {"query": "Project A"}),
        ("discover_project_memory", {"query": "Project A"}),
        ("get_project_memory", {"record_id": decision.id}),
        ("check_project_memory", {}),
        ("list_capabilities", {}),
        ("list_agents", {}),
        ("list_skills", {}),
        ("get_skill", skill_args),
        ("get_skill_resource", {**skill_args, "path": "references/guide.md"}),
    )

    async def scenario() -> None:
        async with Client(create_mcp(sdk, policy)) as authorized:
            for name, arguments in guarded_calls:
                result = await authorized.call_tool(name, arguments)
                assert not result.is_error, (name, result.content)
            decisions = await authorized.call_tool("get_decisions", {"topic": "Project A"})
            assert decision.id in decisions.model_dump_json()
            resource = await authorized.read_resource("orqalis://decisions")
            assert decision.id in resource.model_dump_json()
        async with Client(create_mcp(sdk, wrong_policy)) as denied:
            for name, arguments in guarded_calls:
                result = await denied.call_tool(name, arguments)
                assert result.is_error, (name, result.content)
                assert "not_found" in result.model_dump_json(), (name, result.content)
                assert decision.id not in result.model_dump_json()
                assert "Project A guidance" not in result.model_dump_json()

    try:
        asyncio.run(scenario())
    finally:
        sdk.close()
        other_sdk.close()
