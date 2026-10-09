"""Execute a real parallel/repair run with an injected provider for trace QA."""

import asyncio
from pathlib import Path

from orqalis.core.vertical_plan import VerticalPlanner
from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.agent import AgentRole
from orqalis.domain.capabilities import ToolName
from orqalis.domain.execution import CriterionReview, ExecutionPolicy, ReviewResult, WorkerResult
from orqalis.domain.plan import TaskPlan
from orqalis.domain.projections import RunSnapshot
from orqalis.domain.provider import (
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderToolCall,
)
from orqalis.domain.run import RunState
from orqalis.domain.task import Task, TaskDependency
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis
from tests.support.filesystem import filesystem_uow_factory


async def execute_trace_fixture(repository: Path, workers: Path) -> RunSnapshot:
    sdk = Orqalis(unit_of_work=filesystem_uow_factory(repository))
    project = sdk.initialize(repository)
    state = sdk.prepare_run(
        project.id,
        "Inspect and repair the answer",
        "feature/trace-fixture",
        GoalDraft(
            goal="Inspect and repair the answer",
            scope=("main.py",),
            definition_of_done=("Source evidence and independent review pass",),
            criteria=(
                CriterionDefinition(
                    key="AC-1",
                    description="Answer is 43",
                    validation_spec=FileValidation(path="main.py", contains="answer = 43"),
                ),
            ),
        ),
    )
    assert state.goal
    sdk.pause(state.run.id, "trace:pause")
    sdk.resume(state.run.id, "trace:resume")
    base = VerticalPlanner().plan(state.goal, sdk.memory.context(project, "architecture"))
    preparation = tuple(
        Task(
            run_id=state.run.id,
            description=f"Inspect independent concern {i}",
            expected_outcome="Structured context result",
            preferred_role=AgentRole.ARCHITECT,
            validation_method="Source inspection",
            acceptance_criterion_ids=base.tasks[0].acceptance_criterion_ids,
        )
        for i in range(2)
    )
    plan = TaskPlan(
        run_id=state.run.id,
        goal_version_id=state.goal.goal.id,
        version=1,
        tasks=(*preparation, *base.tasks),
        dependencies=(
            *base.dependencies,
            *(
                TaskDependency(
                    task_id=base.tasks[0].id,
                    depends_on_task_id=task.id,
                )
                for task in preparation
            ),
        ),
    )
    sdk.orchestrator.install_plan(plan, "trace:plan")
    sdk.orchestrator.advance(state.run.id, RunState.PLANNED, "trace:planned")
    entered = 0
    together = asyncio.Event()

    async def respond(request: ProviderExecutionRequest) -> ProviderExecutionResult:
        nonlocal entered
        if request.role == AgentRole.ARCHITECT:
            entered += 1
            if entered == 2:
                together.set()
            await asyncio.wait_for(together.wait(), timeout=5)
        elif request.role == AgentRole.DEVELOPER and not request.observations:
            return ProviderExecutionResult(
                tool_calls=(
                    ProviderToolCall(
                        id="write-answer",
                        name=ToolName.FILE_WRITE,
                        arguments={
                            "path": "main.py",
                            "content": "answer = 41\n"
                            if request.task.plan_version == 1
                            else "answer = 43\n",
                        },
                    ),
                )
            )
        elif request.role == AgentRole.REVIEWER:
            assert request.acceptance
            passed = all(c.status == "PASS" for c in request.acceptance.criteria)
            return ProviderExecutionResult(
                output=ReviewResult(
                    overall="PASS" if passed else "FAIL",
                    criteria=tuple(
                        CriterionReview(
                            criterion_id=c.id,
                            status="PASS" if c.status == "PASS" else "FAIL",
                            reason="Actual persisted source evidence",
                            evidence_refs=c.evidence_refs[-1:],
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
                summary="private-provider-output-sentinel",
                artifact_paths=("main.py",) if request.role == AgentRole.DEVELOPER else (),
            ).model_dump(mode="json")
        )

    provider = FakeProvider(lambda _: ProviderExecutionResult(output={}))
    provider.execute = respond  # type: ignore[method-assign]
    result = await sdk.executor(workers, (provider,)).execute(
        state.run.id,
        "fixture",
        ExecutionPolicy(write_paths=("main.py",), max_parallel_tasks=2),
    )
    assert result.review and result.review.result.overall == "PASS"
    snapshot = sdk.snapshot(state.run.id)
    sdk.close()
    return snapshot
