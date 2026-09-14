"""Transactional approval check for authoritative workflow transitions.

The workflow driver may create requests ahead of a transition for the UI. This
guard also fails closed when a lower-level Orchestrator method is called directly.
It commits only a newly created pending request, never a workflow mutation.
"""

from uuid import uuid5

from orqalis.core.approvals import ApprovalService, set_approval_actor_status
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit
from orqalis.domain.approval import ApprovalRequest, ApprovalStage, ApprovalStatus, ControlPolicy
from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.run import Run


def require_approval(
    uow: ProjectUnitOfWork,
    run: Run,
    stage: ApprovalStage,
    subject_version: int,
    subject_digest: str,
    reason: str,
) -> None:
    policy = uow.approvals.policy(run.id) or ControlPolicy(run_id=run.id)
    if not policy.requires(stage):
        return
    ApprovalService._safe_fields(subject_digest, reason)
    ApprovalService._validate_subject(run, uow, stage, subject_version)
    request_id = uuid5(run.id, f"approval:{stage}:{subject_version}:{subject_digest}")
    request = uow.approvals.get(request_id)
    if request is None:
        request = ApprovalRequest(
            id=request_id,
            run_id=run.id,
            stage=stage,
            subject_version=subject_version,
            subject_digest=subject_digest,
            reason=reason,
        )
        uow.approvals.add_request(request)
        emit(
            uow,
            run,
            EventType.APPROVAL_REQUESTED,
            f"operator-approval:{request.id}:requested",
            request.created_at,
            EventPayload(
                approval_request_id=request.id,
                approval_stage=stage,
                approval_subject_digest=subject_digest,
                status=ApprovalStatus.PENDING,
                reason=reason,
            ),
        )
        set_approval_actor_status(uow, run, request, ApprovalStatus.PENDING, request.created_at)
        uow.commit()
    if request.status != ApprovalStatus.APPROVED:
        raise PolicyDeniedError(f"{stage.value} approval required: {request.id}")


def require_delivery_binding(uow: ProjectUnitOfWork, run: Run) -> None:
    """Require the exact persisted delivery policy and its operator decision."""
    binding = uow.events.by_key(run.id, "delivery:policy")
    if binding is None:
        raise PolicyDeniedError("Explicit delivery policy is required")
    control = uow.approvals.policy(run.id) or ControlPolicy(run_id=run.id)
    if not control.requires(ApprovalStage.DELIVERY):
        return
    request_id = binding.payload.approval_request_id
    request = uow.approvals.get(request_id) if request_id else None
    reviews = uow.execution.reviews(run.id)
    reviewed_version = reviews[-1].plan_version if reviews else None
    if (
        request is None
        or request.run_id != run.id
        or request.stage != ApprovalStage.DELIVERY
        or request.status != ApprovalStatus.APPROVED
        or request.subject_version != reviewed_version
        or request.subject_digest != binding.payload.approval_subject_digest
    ):
        raise PolicyDeniedError("Exact delivery subject needs operator approval")
