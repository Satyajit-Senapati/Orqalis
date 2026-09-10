import asyncio
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import Engine

from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.agent import AgentRole
from orqalis.domain.execution import CriterionReview, ExecutionPolicy, ReviewResult, WorkerResult
from orqalis.domain.provider import ProviderExecutionRequest, ProviderExecutionResult
from orqalis.persistence.database import session_factory
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis

pytestmark = pytest.mark.postgres


def test_plain_request_requirements_are_durable_and_join_the_plan(
    database: Engine,
    git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    sdk = Orqalis(unit_of_work=factory)
    project = sdk.initialize(git_repo)
    pending = sdk.prepare_run(project.id, "Verify main.py exists", "feature/requirements")
    assert pending.run.state == "ANALYZING" and pending.goal is None
    draft = GoalDraft(
        goal="Verify main.py exists",
        scope=("main.py",),
        constraints=("Preserve source",),
        definition_of_done=("File evidence passes",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="Source exists",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    )

    def respond(request: ProviderExecutionRequest) -> ProviderExecutionResult:
        if request.role == AgentRole.REQUIREMENTS:
            assert request.acceptance is None
            assert not request.allowed_tools
            assert request.context.freshness.fresh
            return ProviderExecutionResult(output=draft.model_dump(mode="json"))
        if request.role == AgentRole.DEVELOPER:
            return ProviderExecutionResult(
                output=WorkerResult(
                    completed=True,
                    summary="Source verified",
                    artifact_paths=("main.py",),
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
                        reason="Checked persisted file evidence",
                        evidence_refs=c.evidence_refs,
                        source_checks=(),
                    )
                    for c in request.acceptance.criteria
                ),
                blocking_findings=(),
                non_blocking_findings=(),
            ).model_dump(mode="json")
        )

    provider = FakeProvider(respond)
    define = sdk.goals.define_initial

    def define_then_crash(run_id: UUID, execution_id: UUID, goal: GoalDraft) -> None:
        define(run_id, execution_id, goal)
        raise RuntimeError("crash after initial goal persisted")

    with monkeypatch.context() as patch:
        patch.setattr(sdk.goals, "define_initial", define_then_crash)
        with pytest.raises(RuntimeError):
            asyncio.run(sdk.requirements((provider,)).define(pending.run.id, "fixture"))
    assert provider.calls == 1
    restarted = Orqalis(unit_of_work=factory)
    goal = asyncio.run(restarted.requirements((provider,)).define(pending.run.id, "fixture"))
    assert provider.calls == 1 and all(c.status == "PENDING" for c in goal.criteria)
    defined = restarted.snapshot(pending.run.id)
    assert defined.run.state == "GOAL_DEFINED"
    assert len(defined.preparation_tasks) == 1
    assert defined.preparation_tasks[0].status == "SUCCEEDED"
    result = asyncio.run(
        restarted.executor(tmp_path / "workers", (provider,)).execute(
            pending.run.id,
            "fixture",
            ExecutionPolicy(write_paths=("main.py",)),
        )
    )
    assert result.review and result.review.result.overall == "PASS"
    snapshot = restarted.snapshot(pending.run.id)
    assert snapshot.plan and len(snapshot.plan.tasks) == 4
    assert snapshot.preparation_tasks[0] in snapshot.plan.tasks
    assert snapshot.plan_completion == 100
    assert snapshot.actors[1].session.role == AgentRole.REQUIREMENTS
    assert snapshot.actors[1].session.completed_at
    assert provider.calls == 3
