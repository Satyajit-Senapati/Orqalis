import json
import os
import subprocess

from orqalis.domain.acceptance import (
    CriterionDefinition,
    FileValidation,
    GoalDraft,
    ReviewValidation,
)
from orqalis.domain.agent import AgentRole
from orqalis.domain.plan import TaskPlan
from orqalis.domain.run import RunState
from orqalis.domain.task import Task, TaskDependency, TaskStatus
from orqalis.evaluation.validators import LocalEvaluator
from orqalis.sdk import Orqalis
from tests.e2e.fixture_paths import fixture_root, pointer_path

root = fixture_root() / "mission-control-fixture"
root.mkdir(parents=True, exist_ok=True)


def git(*args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Orqalis QA",
            "-c",
            "user.email=qa@orqalis.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-C",
            str(root),
            *args,
        ],
        check=True,
        capture_output=True,
    )


if not (root / ".git").exists():
    git("init", "-b", "main")
    (root / "main.py").write_text(
        "def normalize_name(value: str) -> str:\n    return value.strip()\n"
    )
    (root / "README.md").write_text(
        "# Mission Control integration fixture\n"
        "A disposable local fixture for browser verification.\n"
    )
    git("add", ".")
    git("commit", "-m", "test: create Mission Control fixture")
sdk = Orqalis(root=root)
project = sdk.initialize(root)
draft = GoalDraft(
    goal="Validate repository behavior",
    scope=("main.py",),
    constraints=("Preserve unrelated files",),
    definition_of_done=("Deterministic checks pass and review evidence is recorded",),
    criteria=(
        CriterionDefinition(
            key="AC-001",
            description="Name normalization trims whitespace",
            validation_spec=FileValidation(path="main.py", contains="value.strip()"),
        ),
        CriterionDefinition(
            key="AC-002",
            description="Review confirms the change stays within scope",
            validation_spec=ReviewValidation(instructions="Review the accepted diff"),
        ),
    ),
)
state = sdk.prepare_run(
    project.id, "Mission Control integration fixture", "feature/control-center-check", draft
)
assert state.goal is not None
first_id, second_id = (criterion.id for criterion in state.goal.criteria)
tasks = (
    Task(
        run_id=state.run.id,
        description="Inspect name normalization",
        expected_outcome="Source inspected",
        preferred_role=AgentRole.DEVELOPER,
        validation_method="file assertion",
        acceptance_criterion_ids=(first_id,),
    ),
    Task(
        run_id=state.run.id,
        description="Validate normalization behavior",
        expected_outcome="Evidence recorded",
        preferred_role=AgentRole.TESTER,
        validation_method="file assertion",
        acceptance_criterion_ids=(first_id,),
    ),
    Task(
        run_id=state.run.id,
        description="Review scope and acceptance",
        expected_outcome="Structured review",
        preferred_role=AgentRole.REVIEWER,
        validation_method="review evidence",
        acceptance_criterion_ids=(second_id,),
    ),
)
plan = TaskPlan(
    run_id=state.run.id,
    goal_version_id=state.goal.goal.id,
    version=1,
    tasks=tasks,
    dependencies=(
        TaskDependency(task_id=tasks[1].id, depends_on_task_id=tasks[0].id),
        TaskDependency(task_id=tasks[2].id, depends_on_task_id=tasks[1].id),
    ),
)
sdk.orchestrator.install_plan(plan, "qa:plan")
sdk.orchestrator.advance(state.run.id, RunState.PLANNED, "qa:planned")
sdk.orchestrator.advance(state.run.id, RunState.EXECUTING, "qa:execute")
attempt = sdk.orchestrator.start_task(state.run.id, tasks[0].id, "qa:inspect")
assert "value.strip()" in (root / "main.py").read_text()
sdk.orchestrator.transition_task(state.run.id, attempt.id, TaskStatus.SUCCEEDED, "qa:inspected")
sdk.orchestrator.advance(state.run.id, RunState.INTEGRATING, "qa:integrating")
sdk.orchestrator.advance(state.run.id, RunState.TESTING, "qa:testing")
active = sdk.orchestrator.start_task(state.run.id, tasks[1].id, "qa:test")
sdk.goals.validate(state.run.id, "AC-001", LocalEvaluator(root), "qa:validation")
record = {
    "run_id": str(state.run.id),
    "attempt_id": str(active.id),
    "repo": str(root),
    "fixture_root": str(root.parent),
}
pointer_path("ui-fixture.json").write_text(json.dumps(record), encoding="utf-8")
print(json.dumps(record))
sdk.close()
