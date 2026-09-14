from pathlib import Path
from uuid import uuid4

import pytest

from orqalis.agents.routing import CapabilityRouter
from orqalis.core.repair import RepairPlanner
from orqalis.core.vertical_plan import VerticalPlanner
from orqalis.domain.acceptance import AcceptanceCriterion, FileValidation, GoalContract, GoalVersion
from orqalis.domain.agent import AgentRole
from orqalis.domain.capabilities import PermissionProfile, ToolName
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
        (("web/App.tsx",), ()),
        (("README.md",), ()),
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
        tags=("Python", "TypeScript"),
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
