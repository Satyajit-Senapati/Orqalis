import asyncio
from pathlib import Path

import pytest

from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.agent import AgentRole
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.domain.execution import CriterionReview, ExecutionPolicy, ReviewResult, WorkerResult
from orqalis.domain.project import ProjectSettings
from orqalis.domain.provider import (
    ProviderErrorCode,
    ProviderExecutionRequest,
    ProviderExecutionResult,
)
from orqalis.providers.errors import ProviderError
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis
from tests.support.filesystem import filesystem_uow_factory


@pytest.mark.parametrize("attempt_limit", [1, 3])
def test_explicit_recovery_uses_new_attempt_preserves_contract_and_enforces_limit(
    git_repo: Path,
    tmp_path: Path,
    attempt_limit: int,
) -> None:
    sdk = Orqalis(unit_of_work=filesystem_uow_factory(git_repo))
    project = sdk.initialize(git_repo, ProjectSettings(max_task_attempts=attempt_limit))
    state = sdk.prepare_run(
        project.id,
        "Check source",
        "feature/recovery",
        GoalDraft(
            goal="Check source",
            scope=("main.py",),
            definition_of_done=("Evidence-backed pass",),
            criteria=(
                CriterionDefinition(
                    key="AC-1",
                    description="Source exists",
                    validation_spec=FileValidation(path="main.py"),
                ),
            ),
        ),
    )
    policy = ExecutionPolicy(write_paths=("main.py",))
    fail = True

    def respond(request: ProviderExecutionRequest) -> ProviderExecutionResult:
        if fail:
            raise ProviderError(ProviderErrorCode.UNAVAILABLE)
        if request.role == AgentRole.DEVELOPER:
            return ProviderExecutionResult(
                output=WorkerResult(
                    completed=True,
                    summary="Source exists",
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
                        reason="Verified file evidence",
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
    executor = sdk.executor(tmp_path / "workers", (provider,))
    with pytest.raises(ProviderError):
        asyncio.run(executor.execute(state.run.id, "fixture", policy))
    blocked = sdk.snapshot(state.run.id)
    assert blocked.run.state == "BLOCKED"
    attempt = blocked.attempts[-1]
    args = (state.run.id, attempt.id, "Provider restored; no tool effects occurred", "recover-1")
    with pytest.raises(PolicyDeniedError):
        sdk.orchestrator.recover_task(*args)
    with sdk.unit_of_work() as lease:
        assert lease.execution.try_run_lock(state.run.id)
        with pytest.raises(ConflictError):
            sdk.orchestrator.recover_task(*args, acknowledge_uncertainty=True)
    if attempt_limit == 1:
        with pytest.raises(PolicyDeniedError, match="limit"):
            sdk.orchestrator.recover_task(*args, acknowledge_uncertainty=True)
        return
    task = sdk.orchestrator.recover_task(*args, acknowledge_uncertainty=True)
    assert task.status == "READY" and task.attempt_count == 1
    assert sdk.orchestrator.recover_task(*args, acknowledge_uncertainty=True) == task
    assert sdk.goals.get(state.run.id) == state.goal
    sdk.resume(state.run.id, "resume-after-recovery")
    fail = False
    result = asyncio.run(executor.execute(state.run.id, "fixture", policy))
    assert result.review and result.review.result.overall == "PASS"
    restored = sdk.snapshot(state.run.id)
    history = [a for a in restored.attempts if a.task_id == task.id]
    assert [a.status for a in history] == ["FAILED", "SUCCEEDED"]
    assert history[1].attempt == 2 and history[0].id != history[1].id
    assert restored.task_timing[task.id].active_ms >= history[0].active_ms + history[1].active_ms
    assert restored.goal and state.goal and restored.goal.goal == state.goal.goal
    assert provider.calls == 3
