import asyncio
from pathlib import Path

import pytest
from sqlalchemy import Engine

from orqalis.core.vertical_plan import VerticalPlanner
from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.agent import AgentRole
from orqalis.domain.errors import ConflictError
from orqalis.domain.execution import CriterionReview, ExecutionPolicy, ReviewResult, WorkerResult
from orqalis.domain.provider import ProviderExecutionRequest, ProviderExecutionResult
from orqalis.domain.run import RunState
from orqalis.domain.task import TaskStatus
from orqalis.persistence.database import session_factory
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis

pytestmark = pytest.mark.postgres


def test_revised_goal_replans_without_rewriting_prior_history(
    database: Engine,
    git_repo: Path,
    tmp_path: Path,
) -> None:
    sdk = Orqalis(unit_of_work=lambda: SQLProjectUnitOfWork(session_factory(database)))
    project = sdk.initialize(git_repo)
    draft = GoalDraft(
        goal="Inspect source",
        scope=("main.py",),
        definition_of_done=("Source exists",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="Source exists",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    )
    state = sdk.prepare_run(project.id, "Inspect source", "feature/replan", draft)
    assert state.goal
    old_plan = VerticalPlanner().plan(state.goal, sdk.memory.context(project, "source"))
    sdk.orchestrator.install_plan(old_plan, "initial")
    sdk.orchestrator.advance(state.run.id, RunState.PLANNED, "planned")
    sdk.orchestrator.advance(state.run.id, RunState.EXECUTING, "vertical:1:executing")
    attempt = sdk.orchestrator.start_task(state.run.id, old_plan.tasks[0].id, "inspect")
    sdk.orchestrator.transition_task(state.run.id, attempt.id, TaskStatus.SUCCEEDED, "inspected")
    sdk.pause(state.run.id, "pause")
    revised_draft = draft.model_copy(
        update={
            "goal": "Inspect source under the clarified scope",
            "constraints": ("Keep the existing answer",),
        }
    )
    revised = sdk.goals.revise(state.run.id, revised_draft, "User clarified scope", 1)
    with pytest.raises(ConflictError):
        sdk.resume(state.run.id, "premature-resume")
    replanned = sdk.replan(state.run.id, "replan")
    assert replanned.state == "PAUSED" and replanned.resume_state == "PLANNED"
    assert sdk.replan(state.run.id, "replan") == replanned
    with sdk.unit_of_work() as uow:
        previous = uow.runtime.get_plan(state.run.id, 1)
        current = uow.runtime.get_plan(state.run.id, 2)
        assert previous and current
        assert next(t for t in previous.tasks if t.id == old_plan.tasks[0].id).status == "SUCCEEDED"
        assert all(t.status == "CANCELLED" for t in previous.tasks if t.id != old_plan.tasks[0].id)
        assert not {t.id for t in previous.tasks} & {t.id for t in current.tasks}
        assert current.goal_version_id == revised.goal.id
        assert uow.runs.get_goal(state.goal.goal.id) == state.goal
    sdk.resume(state.run.id, "resume")

    def respond(request: ProviderExecutionRequest) -> ProviderExecutionResult:
        if request.role == AgentRole.DEVELOPER:
            return ProviderExecutionResult(
                output=WorkerResult(
                    completed=True, summary="Inspected unchanged source", artifact_paths=()
                ).model_dump(mode="json")
            )
        assert request.acceptance
        return ProviderExecutionResult(
            output=ReviewResult(
                overall="PASS",
                criteria=tuple(
                    CriterionReview(
                        criterion_id=c.id,
                        status="PASS",
                        reason="Current file evidence",
                        evidence_refs=c.evidence_refs,
                        source_checks=(),
                    )
                    for c in request.acceptance.criteria
                ),
                blocking_findings=(),
                non_blocking_findings=(),
            ).model_dump(mode="json")
        )

    result = asyncio.run(
        sdk.executor(tmp_path / "workers", (FakeProvider(respond),)).execute(
            state.run.id, "fixture", ExecutionPolicy(write_paths=("main.py",))
        )
    )
    assert result.review and result.review.goal_version_id == revised.goal.id
    assert sdk.snapshot(state.run.id).plan_completion == 100
