"""Filesystem-backed regression coverage for supervised delivery and repair gates."""

import asyncio
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.agent import AgentRole
from orqalis.domain.approval import ApprovalDecisionKind, ApprovalStage, ApprovalStatus, ControlMode
from orqalis.domain.capabilities import ToolName
from orqalis.domain.delivery import DeliveryPolicy
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.domain.events import EventType
from orqalis.domain.execution import (
    CriterionReview,
    ExecutionPolicy,
    ReviewResult,
    WorkerResult,
)
from orqalis.domain.provider import (
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderToolCall,
)
from orqalis.domain.run import RunState
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis


def _approve_latest(sdk: Orqalis, run_id: UUID, stage: ApprovalStage) -> None:
    request = sdk.approvals.list(run_id)[-1]
    assert request.stage == stage and request.status == ApprovalStatus.PENDING
    sdk.approvals.decide(
        run_id,
        request.id,
        ApprovalDecisionKind.APPROVE,
        "integration-operator",
        request.subject_digest,
        f"Reviewed {stage.value.lower()} subject",
    )


def _reviewed_run(git_repo: Path, tmp_path: Path, *, reviewer_passes: bool) -> tuple[Orqalis, UUID]:
    sdk = Orqalis(root=git_repo)
    factory = sdk.unit_of_work
    project = sdk.initialize(git_repo)
    goal = GoalDraft(
        goal="Set answer to 43",
        scope=("main.py",),
        definition_of_done=("Source exists and reviewer checks the implementation",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="Source file exists",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    )
    prepared = sdk.prepare_run(
        project.id,
        "Set answer to 43",
        f"feature/supervised-{uuid4().hex[:8]}",
        goal,
        ControlMode.SUPERVISED,
    )
    run_id = prepared.run.id

    def respond(request: ProviderExecutionRequest) -> ProviderExecutionResult:
        if request.role == AgentRole.DEVELOPER:
            if not request.observations:
                return ProviderExecutionResult(
                    tool_calls=(
                        ProviderToolCall(
                            id="write-answer",
                            name=ToolName.FILE_WRITE,
                            arguments={"path": "main.py", "content": "answer = 43\n"},
                        ),
                    )
                )
            return ProviderExecutionResult(
                output=WorkerResult(
                    summary="Set the answer to 43", completed=True, artifact_paths=("main.py",)
                ).model_dump(mode="json")
            )
        if request.role == AgentRole.REVIEWER:
            assert request.acceptance is not None
            verdict = "PASS" if reviewer_passes else "FAIL"
            return ProviderExecutionResult(
                output=ReviewResult(
                    overall=verdict,
                    criteria=tuple(
                        CriterionReview(
                            criterion_id=item.id,
                            status=verdict,
                            reason="Verified source and evidence"
                            if reviewer_passes
                            else "Implementation does not meet the requested behavior",
                            evidence_refs=item.evidence_refs,
                            source_checks=(),
                        )
                        for item in request.acceptance.criteria
                    ),
                    blocking_findings=(),
                    non_blocking_findings=(),
                ).model_dump(mode="json")
            )
        return ProviderExecutionResult(
            output=WorkerResult(
                summary="Context checked", completed=True, artifact_paths=()
            ).model_dump(mode="json")
        )

    executor = sdk.executor(tmp_path / "worktrees", (FakeProvider(respond),))
    policy = ExecutionPolicy(write_paths=("main.py",))
    with pytest.raises(PolicyDeniedError, match="Goal approval required"):
        asyncio.run(executor.execute(run_id, "fixture", policy))
    _approve_latest(sdk, run_id, ApprovalStage.GOAL)
    with pytest.raises(PolicyDeniedError, match="Plan approval required"):
        asyncio.run(executor.execute(run_id, "fixture", policy))
    _approve_latest(sdk, run_id, ApprovalStage.PLAN)
    if reviewer_passes:
        result = asyncio.run(executor.execute(run_id, "fixture", policy))
        assert result.review is not None and result.review.result.overall == "PASS"
        assert result.state == RunState.REVIEWING
    else:
        with pytest.raises(PolicyDeniedError, match="Repair approval required"):
            asyncio.run(executor.execute(run_id, "fixture", policy))
        with factory() as uow:
            reviews = uow.execution.reviews(run_id)
        assert len(reviews) == 1 and reviews[0].result.overall == "FAIL"
    return sdk, run_id


def test_delivery_requires_exact_approved_policy_before_finalization(
    git_repo: Path, tmp_path: Path
) -> None:
    sdk, run_id = _reviewed_run(git_repo, tmp_path, reviewer_passes=True)
    policy = DeliveryPolicy(author_name="Orqalis Test", author_email="test@orqalis.invalid")
    with pytest.raises(PolicyDeniedError, match="Delivery approval required"):
        asyncio.run(sdk.delivery.finalize(run_id, policy))
    delivery_request = sdk.approvals.list(run_id)[-1]
    assert delivery_request.stage == ApprovalStage.DELIVERY
    assert delivery_request.status == ApprovalStatus.PENDING
    assert sdk.snapshot(run_id).run.state == RunState.REVIEWING
    assert sdk.snapshot(run_id).run.plan_version == 1
    with sdk.unit_of_work() as uow:
        assert uow.events.by_key(run_id, "delivery:policy") is None
        assert uow.delivery.get(run_id) is None

    _approve_latest(sdk, run_id, ApprovalStage.DELIVERY)
    # An approved digest for one policy cannot authorize a different policy.
    changed = policy.model_copy(update={"max_deleted_line_ratio": 0.75})
    with pytest.raises(PolicyDeniedError, match="Delivery approval required"):
        asyncio.run(sdk.delivery.finalize(run_id, changed))
    changed_request = sdk.approvals.list(run_id)[-1]
    assert changed_request.stage == ApprovalStage.DELIVERY
    assert changed_request.status == ApprovalStatus.PENDING
    assert changed_request.subject_digest != delivery_request.subject_digest
    with sdk.unit_of_work() as uow:
        assert uow.events.by_key(run_id, "delivery:policy") is None

    delivered = asyncio.run(sdk.delivery.finalize(run_id, policy))
    assert delivered.state == RunState.COMPLETED and delivered.commit_sha
    with sdk.unit_of_work() as uow:
        binding = uow.events.by_key(run_id, "delivery:policy")
        assert binding is not None
        assert binding.payload.approval_request_id == delivery_request.id
        assert binding.payload.approval_subject_digest == delivery_request.subject_digest
        assert (
            len([e for e in uow.events.list(run_id) if e.idempotency_key == "delivery:policy"]) == 1
        )
    assert asyncio.run(sdk.delivery.finalize(run_id, policy)) == delivered
    with pytest.raises(ConflictError, match="policy differs"):
        asyncio.run(sdk.delivery.finalize(run_id, changed))


def test_failed_review_requires_repair_then_new_plan_approval(
    git_repo: Path, tmp_path: Path
) -> None:
    sdk, run_id = _reviewed_run(git_repo, tmp_path, reviewer_passes=False)
    request = sdk.approvals.list(run_id)[-1]
    assert request.stage == ApprovalStage.REPAIR
    assert request.status == ApprovalStatus.PENDING
    assert sdk.snapshot(run_id).run.state == RunState.REVIEWING
    assert sdk.snapshot(run_id).run.plan_version == 1
    with pytest.raises(PolicyDeniedError, match="REPAIR approval required"):
        sdk.orchestrator.advance(run_id, RunState.REPAIR_PLANNING, "direct:repair")
    _approve_latest(sdk, run_id, ApprovalStage.REPAIR)

    with pytest.raises(PolicyDeniedError, match="PLAN approval required"):
        sdk.executor(tmp_path / "worktrees").repair.schedule(run_id)
    snapshot = sdk.snapshot(run_id)
    assert snapshot.run.state == RunState.REPAIR_PLANNING
    assert snapshot.run.plan_version == 2
    assert snapshot.run.repair_iteration == 1
    assert snapshot.plan is not None
    added = [task for task in snapshot.plan.tasks if task.plan_version == 2]
    assert len(added) == 4
    assert (
        len([edge for edge in snapshot.plan.dependencies if edge.task_id in {t.id for t in added}])
        >= 3
    )
    plan_request = sdk.approvals.list(run_id)[-1]
    assert plan_request.stage == ApprovalStage.PLAN
    assert plan_request.subject_version == 2
    assert plan_request.status == ApprovalStatus.PENDING
    with pytest.raises(PolicyDeniedError, match="PLAN approval required"):
        sdk.orchestrator.advance(run_id, RunState.EXECUTING, "direct:repair-execute")

    _approve_latest(sdk, run_id, ApprovalStage.PLAN)
    assert sdk.executor(tmp_path / "worktrees").repair.schedule(run_id)
    assert sdk.snapshot(run_id).run.state == RunState.EXECUTING
    assert sdk.snapshot(run_id).run.plan_version == 2
    with sdk.unit_of_work() as uow:
        events = uow.events.list(run_id)
    assert sum(event.event_type == EventType.REPAIR_REQUESTED for event in events) == 1
