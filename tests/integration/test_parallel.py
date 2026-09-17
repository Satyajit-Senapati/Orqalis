import asyncio
from datetime import timedelta
from pathlib import Path

import pytest

from orqalis.core.vertical_plan import VerticalPlanner
from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.agent import AgentRole
from orqalis.domain.capabilities import ToolName
from orqalis.domain.execution import CriterionReview, ExecutionPolicy, ReviewResult, WorkerResult
from orqalis.domain.plan import TaskPlan
from orqalis.domain.provider import ProviderExecutionRequest, ProviderExecutionResult
from orqalis.domain.run import RunState
from orqalis.domain.task import Task, TaskDependency
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis
from tests.support.filesystem import filesystem_uow_factory


def test_independent_context_workers_execute_in_parallel_before_dependency(
    git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk = Orqalis(unit_of_work=filesystem_uow_factory(git_repo))
    project = sdk.initialize(git_repo)
    state = sdk.prepare_run(
        project.id,
        "Inspect two concerns",
        "feature/parallel",
        GoalDraft(
            goal="Inspect two concerns",
            scope=("main.py",),
            definition_of_done=("Evidence passes",),
            criteria=(
                CriterionDefinition(
                    key="AC-1",
                    description="Source exists",
                    validation_spec=FileValidation(path="main.py"),
                ),
            ),
        ),
    )
    assert state.goal
    base = VerticalPlanner().plan(state.goal, sdk.memory.context(project, "architecture"))
    preparation = tuple(
        Task(
            run_id=state.run.id,
            description=f"Inspect concern {i}",
            expected_outcome="Structured context result",
            preferred_role=AgentRole.ARCHITECT,
            validation_method="Source inspection",
            acceptance_criterion_ids=base.tasks[0].acceptance_criterion_ids,
        )
        for i in range(2)
    )
    second_developer = Task(
        run_id=state.run.id,
        description="Inspect after the first developer",
        created_at=base.tasks[0].created_at - timedelta(seconds=1),
        expected_outcome="Ordered implementation follow-up",
        preferred_role=AgentRole.DEVELOPER,
        validation_method="File evidence",
        acceptance_criterion_ids=base.tasks[0].acceptance_criterion_ids,
    )
    plan = TaskPlan(
        run_id=state.run.id,
        goal_version_id=state.goal.goal.id,
        version=1,
        tasks=(second_developer, *preparation, *base.tasks),
        dependencies=(
            *base.dependencies,
            TaskDependency(task_id=second_developer.id, depends_on_task_id=base.tasks[0].id),
            TaskDependency(task_id=base.tasks[1].id, depends_on_task_id=second_developer.id),
            *(
                TaskDependency(task_id=base.tasks[0].id, depends_on_task_id=t.id)
                for t in preparation
            ),
        ),
    )
    sdk.orchestrator.install_plan(plan, "parallel:plan")
    sdk.orchestrator.advance(state.run.id, RunState.PLANNED, "parallel:planned")
    provider = FakeProvider(lambda _: ProviderExecutionResult(output={}))
    entered = 0
    together = asyncio.Event()

    async def respond(request: ProviderExecutionRequest) -> ProviderExecutionResult:
        nonlocal entered
        if request.role == AgentRole.ARCHITECT:
            assert ToolName.FILE_WRITE not in {t.name for t in request.allowed_tools}
            entered += 1
            if entered == 2:
                together.set()
            await asyncio.wait_for(together.wait(), timeout=5)
        elif request.role == AgentRole.DEVELOPER:
            assert entered == 2
            checkpoint = sdk.snapshot(state.run.id)
            assert checkpoint.plan
            if request.task.id == second_developer.id:
                assert (
                    next(t for t in checkpoint.plan.tasks if t.id == base.tasks[0].id).status
                    == "SUCCEEDED"
                )
            assert all(
                t.status == "SUCCEEDED"
                for t in checkpoint.plan.tasks
                if t.preferred_role == AgentRole.ARCHITECT
            )
        elif request.role == AgentRole.REVIEWER:
            assert request.acceptance
            return ProviderExecutionResult(
                output=ReviewResult(
                    overall="PASS",
                    criteria=tuple(
                        CriterionReview(
                            criterion_id=c.id,
                            status="PASS",
                            reason="Actual file evidence",
                            evidence_refs=c.evidence_refs,
                            source_checks=(),
                        )
                        for c in request.acceptance.criteria
                    ),
                    blocking_findings=(),
                    non_blocking_findings=(),
                ).model_dump(mode="json")
            )
        return ProviderExecutionResult(
            output=WorkerResult(
                completed=True,
                summary="Context and source inspected",
                artifact_paths=(),
            ).model_dump(mode="json")
        )

    monkeypatch.setattr(provider, "execute", respond)
    result = asyncio.run(
        sdk.executor(tmp_path / "workers", (provider,)).execute(
            state.run.id,
            "fixture",
            ExecutionPolicy(write_paths=("main.py",), max_parallel_tasks=2),
        )
    )
    assert result.review and result.review.result.overall == "PASS"
    snapshot = sdk.snapshot(state.run.id)
    assert snapshot.statistics.max_parallel_tasks == 2
    assert snapshot.statistics.provider_calls == 5
    assert snapshot.plan_completion == 100
