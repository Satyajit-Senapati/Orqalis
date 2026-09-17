from pathlib import Path

from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.execution import ExecutionPolicy
from orqalis.sdk import Orqalis


def test_external_documentation_task_loads_scoped_skill(git_repo: Path, tmp_path: Path) -> None:
    sdk = Orqalis(root=git_repo)
    project = sdk.initialize(git_repo)
    goal = GoalDraft(
        goal="Update the repository instructions",
        scope=("AGENTS.md",),
        definition_of_done=("Instructions remain available",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="Instructions exist",
                validation_spec=FileValidation(path="AGENTS.md"),
            ),
        ),
    )
    state = sdk.prepare_run(project.id, goal.goal, "feature/docs-skill", goal)
    work = sdk.external_work(tmp_path / "worktrees").next_work(
        state.run.id,
        ExecutionPolicy(write_paths=("AGENTS.md",), command_mode="trusted_local"),
    )
    assert work is not None
    assert work.task.required_capabilities == ("documentation",)
    assert tuple(skill.metadata.id for skill in work.skills) == ("documentation-edit",)
