"""External issues remain untrusted until an independent review verifies resolution."""

import asyncio
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import Engine

from orqalis.delivery.gates import guard_delivery
from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.delivery import DeliveryPolicy, FinalValidation
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.domain.execution import (
    CriterionReview,
    ExecutionPolicy,
    FindingReview,
    ReviewResult,
    SourceCheck,
    WorkerResult,
)
from orqalis.domain.external import FindingReport
from orqalis.domain.provider import ProviderExecutionRequest, ProviderExecutionResult
from orqalis.domain.run import RunState
from orqalis.domain.task import TaskExecution
from orqalis.evaluation.validators import LocalEvaluator
from orqalis.persistence.database import session_factory
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis

pytestmark = pytest.mark.postgres


def test_external_finding_failure_repairs_then_resolves_independently(
    database: Engine, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    sdk = Orqalis(unit_of_work=factory)
    project = sdk.initialize(git_repo)
    goal = GoalDraft(
        goal="Keep module and correct the reported behavior",
        scope=("main.py",),
        definition_of_done=("Independent review verifies reported issues",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="Module remains available",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    )
    state = sdk.prepare_run(project.id, goal.goal, "feature/finding-repair", goal)
    policy = ExecutionPolicy(write_paths=("main.py",), command_mode="trusted_local")
    external = sdk.external_work(tmp_path / "worktrees")
    work = external.next_work(state.run.id, policy)
    assert work is not None
    report = FindingReport(
        severity="blocking", summary="Answer must become 43", source_ref="main.py"
    )
    finding = external.report_finding(state.run.id, work.execution.id, report, "source-issue")
    assert finding.task_id == work.task.id
    external.report(
        state.run.id,
        work.execution.id,
        WorkerResult(summary="Ready for independent inspection", completed=True, artifact_paths=()),
    )
    # A completed worker receipt neither closes an issue nor passes delivery gates.
    with factory() as uow:
        run = uow.runs.get(state.run.id)
        assert run is not None
        with pytest.raises(PolicyDeniedError, match="blocking worker findings"):
            guard_delivery(uow, run, RunState.CHANGE_GUARD)
    reviews = 0

    def respond(request: ProviderExecutionRequest) -> ProviderExecutionResult:
        nonlocal reviews
        reviews += 1
        assert request.role == "reviewer"
        assert len(request.findings) == 1 and request.findings[0].id == finding.id
        assert request.acceptance is not None
        resolved = reviews > 1
        return ProviderExecutionResult(
            output=ReviewResult(
                overall="PASS" if resolved else "FAIL",
                criteria=tuple(
                    CriterionReview(
                        criterion_id=c.id,
                        status="PASS",
                        reason="Observed passing source validator",
                        evidence_refs=c.evidence_refs,
                        source_checks=(),
                    )
                    for c in request.acceptance.criteria
                ),
                blocking_findings=()
                if resolved
                else ("Reported main.py behavior still needs correction",),
                non_blocking_findings=(),
                finding_reviews=(
                    FindingReview(
                        finding_id=finding.id,
                        resolved=resolved,
                        reason="Inspected reported source",
                        source_checks=(SourceCheck(path="main.py", contains="answer = 43"),)
                        if resolved
                        else (),
                    ),
                ),
            ).model_dump(mode="json")
        )

    provider = FakeProvider(respond)
    executor = sdk.executor(tmp_path / "worktrees", (provider,))
    failed = asyncio.run(
        executor.execute(state.run.id, "fixture", policy, repair_automatically=False)
    )
    assert failed.review is not None and failed.review.result.overall == "FAIL"
    assert sdk.snapshot(state.run.id).run.repair_iteration == 1
    assert (
        next(f for f in sdk.snapshot(state.run.id).findings if f.id == finding.id).status == "open"
    )
    for _ in range(2):
        repair = external.next_work(state.run.id, policy)
        assert repair is not None
        if repair.task.preferred_role == "developer":
            (repair.workspace / "main.py").write_text("answer = 43\n", encoding="utf-8")
        external.report(
            state.run.id,
            repair.execution.id,
            WorkerResult(
                summary="Targeted correction inspected", completed=True, artifact_paths=()
            ),
        )
    accepted = asyncio.run(
        executor.execute(state.run.id, "fixture", policy, repair_automatically=False)
    )
    assert accepted.review is not None and accepted.review.result.overall == "PASS"
    assert (
        next(f for f in sdk.snapshot(state.run.id).findings if f.id == finding.id).status
        == "resolved"
    )
    assert (
        external.report_finding(state.run.id, work.execution.id, report, "source-issue").id
        == finding.id
    )
    with factory() as uow:
        run = uow.runs.get(state.run.id)
        assert run is not None
        guard_delivery(uow, run, RunState.CHANGE_GUARD)
    assert reviews == 2
    original_validation = sdk.delivery.validation.validate

    async def mutate_before_validation(run_id: UUID, attempt: TaskExecution) -> FinalValidation:
        (work.workspace / "main.py").write_text("answer = 44\n", encoding="utf-8")
        return await original_validation(run_id, attempt)

    monkeypatch.setattr(sdk.delivery.validation, "validate", mutate_before_validation)
    with pytest.raises(PolicyDeniedError, match="Final validation failed"):
        asyncio.run(sdk.delivery.finalize(state.run.id, DeliveryPolicy()))
    with factory() as uow:
        assert not uow.delivery.validations(state.run.id)[-1].passed
        assert not uow.delivery.get(state.run.id)


@pytest.mark.parametrize(
    "bad_review",
    [
        "omitted",
        "assertion_only",
        "wrong_source",
        "missing_text",
        "unrelated_evidence",
        "criterion_evidence_only",
        "stale_evidence",
    ],
)
def test_worker_findings_cannot_be_waived_without_evidence(
    database: Engine, git_repo: Path, tmp_path: Path, bad_review: str
) -> None:
    sdk = Orqalis(unit_of_work=lambda: SQLProjectUnitOfWork(session_factory(database)))
    project = sdk.initialize(git_repo)
    goal = GoalDraft(
        goal="Inspect worker report",
        scope=("main.py",),
        definition_of_done=("Evidence backs review",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="Module exists",
                validation_spec=FileValidation(path="pyproject.toml"),
            ),
        ),
    )
    state = sdk.prepare_run(project.id, goal.goal, "feature/finding-proof", goal)
    policy = ExecutionPolicy(write_paths=("main.py",), command_mode="trusted_local")
    external = sdk.external_work(tmp_path / "worktrees")
    work = external.next_work(state.run.id, policy)
    assert work is not None
    early_proof = (
        sdk.goals.validate(state.run.id, "AC-1", LocalEvaluator(work.workspace), "before-finding")
        if bad_review == "stale_evidence"
        else None
    )
    finding = external.report_finding(
        state.run.id,
        work.execution.id,
        FindingReport(severity="blocking", summary="Verify answer", source_ref="main.py"),
        "issue",
    )
    external.report(
        state.run.id,
        work.execution.id,
        WorkerResult(summary="Implementation reported", completed=True, artifact_paths=()),
    )

    def respond(request: ProviderExecutionRequest) -> ProviderExecutionResult:
        assert request.acceptance is not None
        verdict = FindingReview(
            finding_id=finding.id,
            resolved=True,
            reason="Asserted resolution",
            source_checks=(
                SourceCheck(
                    path="README.md" if bad_review == "wrong_source" else "main.py",
                    contains="nonexistent marker",
                ),
            )
            if bad_review in {"wrong_source", "missing_text"}
            else (),
            evidence_refs=(early_proof.id,)
            if early_proof is not None
            else (uuid4(),)
            if bad_review == "unrelated_evidence"
            else request.acceptance.criteria[0].evidence_refs
            if bad_review == "criterion_evidence_only"
            else (),
        )
        return ProviderExecutionResult(
            output=ReviewResult(
                overall="PASS",
                criteria=tuple(
                    CriterionReview(
                        criterion_id=c.id,
                        status="PASS",
                        reason="Observed file",
                        evidence_refs=c.evidence_refs,
                        source_checks=(),
                    )
                    for c in request.acceptance.criteria
                ),
                blocking_findings=(),
                non_blocking_findings=(),
                finding_reviews=() if bad_review == "omitted" else (verdict,),
            ).model_dump(mode="json")
        )

    with pytest.raises((ConflictError, PolicyDeniedError)):
        asyncio.run(
            sdk.executor(tmp_path / "worktrees", (FakeProvider(respond),)).execute(
                state.run.id, "fixture", policy
            )
        )
    snapshot = sdk.snapshot(state.run.id)
    assert snapshot.run.state == "BLOCKED"
    assert not snapshot.reviews
    assert next(f for f in snapshot.findings if f.id == finding.id).status == "open"


@pytest.mark.parametrize("path", ["../secret", "/tmp/secret", "C:/private", "..\\secret"])
def test_finding_source_cannot_escape_repository(path: str) -> None:
    with pytest.raises(ValidationError):
        FindingReport(severity="blocking", summary="Invalid source", source_ref=path)


@pytest.mark.parametrize(
    "scenario", ["accepted", "recreated_before_review", "recreated_before_delivery"]
)
def test_deleted_source_finding_uses_matching_absence_evidence_and_revalidates_optional_criterion(
    database: Engine,
    git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    sdk = Orqalis(unit_of_work=factory)
    project = sdk.initialize(git_repo)
    goal = GoalDraft(
        goal="Remove the obsolete module",
        scope=("main.py",),
        definition_of_done=("Reported obsolete source is removed and independently reviewed",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="Project metadata remains",
                validation_spec=FileValidation(path="pyproject.toml"),
            ),
            CriterionDefinition(
                key="AC-2",
                description="Obsolete module is absent",
                priority="optional",
                validation_spec=FileValidation(path="main.py", must_exist=False),
            ),
        ),
    )
    state = sdk.prepare_run(project.id, goal.goal, "feature/finding-deletion", goal)
    policy = ExecutionPolicy(write_paths=("main.py",), command_mode="trusted_local")
    external = sdk.external_work(tmp_path / "worktrees")
    work = external.next_work(state.run.id, policy)
    assert work is not None
    finding = external.report_finding(
        state.run.id,
        work.execution.id,
        FindingReport(
            severity="blocking", summary="Obsolete module must be removed", source_ref="main.py"
        ),
        "deletion",
    )
    (work.workspace / "main.py").unlink()
    external.report(
        state.run.id,
        work.execution.id,
        WorkerResult(summary="Removed obsolete source", completed=True, artifact_paths=()),
    )

    def respond(request: ProviderExecutionRequest) -> ProviderExecutionResult:
        assert request.acceptance is not None
        absence = next(c for c in request.acceptance.criteria if c.key == "AC-2")
        if scenario == "recreated_before_review":
            (work.workspace / "main.py").write_text("answer = 42\n", encoding="utf-8")
        return ProviderExecutionResult(
            output=ReviewResult(
                overall="PASS",
                criteria=tuple(
                    CriterionReview(
                        criterion_id=c.id,
                        status="PASS",
                        reason="Observed current validation",
                        evidence_refs=c.evidence_refs,
                        source_checks=(),
                    )
                    for c in request.acceptance.criteria
                ),
                blocking_findings=(),
                non_blocking_findings=(),
                finding_reviews=(
                    FindingReview(
                        finding_id=finding.id,
                        resolved=True,
                        reason="Current file validator proves absence",
                        evidence_refs=absence.evidence_refs,
                    ),
                ),
            ).model_dump(mode="json")
        )

    executor = sdk.executor(tmp_path / "worktrees", (FakeProvider(respond),))
    if scenario == "recreated_before_review":
        with pytest.raises(ConflictError, match="source changed"):
            asyncio.run(executor.execute(state.run.id, "fixture", policy))
        assert sdk.snapshot(state.run.id).findings[0].status == "open"
        return
    accepted = asyncio.run(executor.execute(state.run.id, "fixture", policy))
    assert accepted.review is not None and accepted.review.result.overall == "PASS"
    assert sdk.snapshot(state.run.id).findings[0].status == "resolved"
    delivery = DeliveryPolicy(
        max_deleted_line_ratio=1.0, author_name="Orqalis Test", author_email="test@orqalis.invalid"
    )
    if scenario == "recreated_before_delivery":
        validate = sdk.delivery.validation.validate

        async def recreate(run_id: UUID, attempt: TaskExecution) -> FinalValidation:
            (work.workspace / "main.py").write_text("answer = 42\n", encoding="utf-8")
            return await validate(run_id, attempt)

        monkeypatch.setattr(sdk.delivery.validation, "validate", recreate)
        with pytest.raises(PolicyDeniedError, match="Final validation failed"):
            asyncio.run(sdk.delivery.finalize(state.run.id, delivery))
        criteria = {c.key: c.status for c in sdk.goals.get(state.run.id).criteria}
        assert criteria == {"AC-1": "PASS", "AC-2": "FAIL"}
        with factory() as uow:
            assert not uow.delivery.validations(state.run.id)[-1].passed
            assert not uow.delivery.get(state.run.id)
        return
    completed = asyncio.run(sdk.delivery.finalize(state.run.id, delivery))
    assert completed.state == "COMPLETED" and completed.commit_sha
    assert not (work.workspace / "main.py").exists()
