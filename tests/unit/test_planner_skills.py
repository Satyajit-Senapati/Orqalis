from pathlib import Path
from uuid import uuid4

import pytest

from orqalis.agents.routing import CapabilityRouter
from orqalis.core.repair import RepairPlanner
from orqalis.core.vertical_plan import VerticalPlanner, implementation_capabilities
from orqalis.domain.acceptance import AcceptanceCriterion, FileValidation, GoalContract, GoalVersion
from orqalis.domain.agent import AgentRole
from orqalis.domain.capabilities import LoadedSkill, PermissionProfile, SkillMetadata, ToolName
from orqalis.domain.errors import InputError
from orqalis.domain.execution import CriterionReview, ReviewRecord, ReviewResult, WorkerResult
from orqalis.domain.memory import ContextPack, MemoryHealth
from orqalis.domain.provider import ProviderExecutionResult
from orqalis.execution.tool_definitions import tool_definitions
from orqalis.providers.fake import FakeProvider
from orqalis.skills.registry import SkillRegistry


def contract(scope: tuple[str, ...]) -> GoalContract:
    goal = GoalVersion(
        run_id=uuid4(),
        version=1,
        goal="Implement scoped behavior",
        scope=scope,
        definition_of_done=("Source check passes",),
    )
    return GoalContract(
        goal=goal,
        criteria=(
            AcceptanceCriterion(
                goal_version_id=goal.id,
                key="AC-1",
                description="Source exists",
                priority="required",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    )


def context() -> ContextPack:
    project = uuid4()
    return ContextPack(
        project_id=project,
        task="Scoped change",
        items=(),
        relevant_files=("src/main.py", "web/App.tsx", "README.md"),
        freshness=MemoryHealth(
            project_id=project,
            indexed_commit="abc",
            current_commit="abc",
            fresh=True,
            dirty_paths=(),
            active_items=0,
        ),
        confidence=1,
        targeted_inspection_paths=(),
        requires_inspection=False,
        size_chars=0,
    )


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        (("main.py",), ("python-edit",)),
        (("src/*",), ("python-edit",)),
        (("src/",), ("python-edit",)),
        (("web/App.tsx",), ("react-edit", "typescript-edit")),
        (("README.md",), ("documentation-edit",)),
        (("Improve developer documentation",), ()),
    ],
)
def test_task_scope_selects_only_applicable_developer_skills(
    scope: tuple[str, ...], expected: tuple[str, ...]
) -> None:
    pack = context()
    task = VerticalPlanner().plan(contract(scope), pack).tasks[0]
    router = CapabilityRouter(
        SkillRegistry((Path(__file__).parents[2] / "src/orqalis/skills/bundled",)),
        (FakeProvider(lambda _: ProviderExecutionResult(output={"summary": "Done"})),),
    )
    _, request = router.prepare(
        task,
        pack,
        uuid4(),
        uuid4(),
        uuid4(),
        "fixture",
        PermissionProfile(allowed_tools=tuple(ToolName)),
        WorkerResult.model_json_schema(),
        tool_definitions(
            (ToolName.FILE_READ, ToolName.FILE_WRITE, ToolName.TEST_RUN, ToolName.GIT_DIFF)
        ),
        tags=("Python", "TypeScript", "JavaScript", "React", "Database", "Documentation"),
    )
    assert tuple(skill.metadata.id for skill in request.selected_skills) == expected
    assert request.task.preferred_role == AgentRole.DEVELOPER


def test_targeted_repair_retains_original_required_skills() -> None:
    goal = contract(("main.py",))
    plan = VerticalPlanner().plan(goal, context())
    review = ReviewRecord(
        run_id=plan.run_id,
        goal_version_id=plan.goal_version_id,
        plan_version=plan.version,
        actor_session_id=uuid4(),
        tree_hash="digest",
        result=ReviewResult(
            overall="FAIL",
            criteria=(
                CriterionReview(
                    criterion_id=goal.criteria[0].id,
                    status="FAIL",
                    reason="Missing required behavior",
                    evidence_refs=(),
                    source_checks=(),
                ),
            ),
            blocking_findings=(),
            non_blocking_findings=(),
        ),
    )
    repaired = RepairPlanner().plan(plan, review, (goal.criteria[0].id,))
    repair = next(
        task
        for task in repaired.tasks
        if task.plan_version == 2 and task.preferred_role == AgentRole.DEVELOPER
    )
    assert repair.required_capabilities == ("implementation", "python")
    assert repaired.goal_version_id == plan.goal_version_id
    assert repair.parent_task_id == plan.tasks[0].id


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        (("src/api.pyi",), ("python",)),
        (("web/new.ts",), ("typescript",)),
        (("web/new.tsx",), ("typescript", "react")),
        (("web/new.jsx",), ("javascript", "react")),
        (("scripts/build.mjs",), ("javascript",)),
        (("web/config.mts",), ("typescript",)),
        (("schema.sql",), ("database",)),
        (("prisma/schema.prisma",), ("database",)),
        (("alembic.ini",), ("database",)),
        (("migrations/001_initial.py",), ("python", "database")),
        (("src/persistence/models.py",), ("python", "database")),
        (("docs/database.md",), ("documentation",)),
        (("docs/database/",), ("documentation",)),
        (("docs/",), ("documentation",)),
        (("README",), ("documentation",)),
        (("web/",), ("typescript", "react")),
        (("web",), ("typescript", "react")),
        (("web/*.tsx",), ("typescript", "react")),
        ((r".\web\App.tsx",), ("typescript", "react")),
        (("README.md", "src/main.py"), ("python", "documentation")),
        (("Improve Python and React documentation",), ()),
        (("missing/",), ()),
        (("./",), ("python", "typescript", "react", "documentation")),
    ],
)
def test_scope_infers_capabilities_without_unrelated_memory_languages(
    scope: tuple[str, ...], expected: tuple[str, ...]
) -> None:
    assert implementation_capabilities(contract(scope), context()) == expected


def test_scope_exclusions_and_directory_boundaries_prevent_skill_leakage() -> None:
    goal = contract(("src/",))
    goal = goal.model_copy(
        update={"goal": goal.goal.model_copy(update={"out_of_scope": ("src/db/",)})}
    )
    pack = context().model_copy(
        update={"relevant_files": ("src/main.py", "src/db/schema.sql", "src-other/App.tsx")}
    )
    assert implementation_capabilities(goal, pack) == ("python",)
    assert implementation_capabilities(contract(("src/db/schema.sql",)), context()) == ("database",)


def test_known_scoped_filename_with_spaces_is_supported() -> None:
    pack = context().model_copy(update={"relevant_files": ("docs/User Guide.md", "src/main.py")})
    assert implementation_capabilities(contract(("docs/User Guide.md",)), pack) == (
        "documentation",
    )


def test_bundled_skill_discovery_is_lazy_and_frontend_skills_remain_separate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = SkillRegistry((Path(__file__).parents[2] / "src/orqalis/skills/bundled",))
    loaded = []
    original_load = registry.load

    def capture(metadata: SkillMetadata) -> LoadedSkill:
        loaded.append(metadata.id)
        return original_load(metadata)

    monkeypatch.setattr(registry, "load", capture)
    catalog = {item.id for item in registry.discover()}
    assert catalog >= {
        "python-edit",
        "python-test",
        "evidence-review",
        "typescript-edit",
        "javascript-edit",
        "react-edit",
        "database-edit",
        "documentation-edit",
    }
    assert loaded == []
    selected = registry.select(
        ("typescript", "react"),
        (ToolName.FILE_READ, ToolName.FILE_WRITE),
        ("typescript", "react", "python", "database", "documentation"),
    )
    assert {skill.metadata.id for skill in selected} == {"typescript-edit", "react-edit"}
    assert set(loaded) == {"typescript-edit", "react-edit"}
    assert all(skill.instructions and len(skill.content_hash) == 64 for skill in selected)


@pytest.mark.parametrize(
    ("capability", "expected"),
    [
        ("python", "python-edit"),
        ("typescript", "typescript-edit"),
        ("javascript", "javascript-edit"),
        ("react", "react-edit"),
        ("database", "database-edit"),
        ("documentation", "documentation-edit"),
    ],
)
def test_bundled_edit_skills_require_scoped_write_tools(capability: str, expected: str) -> None:
    registry = SkillRegistry((Path(__file__).parents[2] / "src/orqalis/skills/bundled",))
    tools = (ToolName.FILE_READ, ToolName.FILE_WRITE)
    selected = registry.select((capability,), tools, (capability,))
    assert tuple(skill.metadata.id for skill in selected) == (expected,)
    assert all(set(skill.metadata.required_tools) <= set(tools) for skill in selected)
    with pytest.raises(InputError):
        registry.select((capability,), (ToolName.FILE_READ,), (capability,))
