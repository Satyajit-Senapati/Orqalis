"""Orchestrator-owned, durable operator approval gates.

An approval authorizes only the exact version and SHA-256 fingerprint requested.
Reviewer evidence and delivery policy attestations do not satisfy this gate.
"""

import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid5

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import (
    emit,
    locked_run,
    orchestrator_actor,
    set_actor_status,
)
from orqalis.domain.agent import ActorStatus
from orqalis.domain.approval import (
    SUPERVISED_GATES,
    ApprovalDecision,
    ApprovalDecisionKind,
    ApprovalRequest,
    ApprovalStage,
    ApprovalStatus,
    ControlMode,
    ControlPolicy,
)
from orqalis.domain.base import utc_now
from orqalis.domain.errors import ConflictError, InputError, NotFoundError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.execution import ExecutionPolicy
from orqalis.domain.run import Run, RunState
from orqalis.domain.task import Task
from orqalis.security.redaction import safe_diagnostic


def fingerprint_subject(payload: object) -> str:
    """Fingerprint a JSON-compatible, versioned subject for an approval gate."""
    normalized = json.loads(json.dumps(payload, default=str))
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def set_approval_actor_status(
    uow: ProjectUnitOfWork,
    run: Run,
    request: ApprovalRequest,
    status: ApprovalStatus,
    at: datetime,
) -> None:
    """Project the operator checkpoint onto the durable Orchestrator actor."""
    actor = orchestrator_actor(uow, run, at)
    if actor.status in {ActorStatus.COMPLETE, ActorStatus.CANCELLED, ActorStatus.FAILED}:
        return
    target = (
        ActorStatus.BLOCKED
        if status == ApprovalStatus.REJECTED
        else ActorStatus.WAITING_FOR_DEPENDENCY
    )
    if actor.status != target:
        set_actor_status(
            uow,
            run,
            actor,
            target,
            f"operator-approval:{request.id}:actor:{status.value.lower()}",
            at,
        )


def task_approval_reason(task: Task, policy: ExecutionPolicy | None) -> str:
    """Provide an operator-readable, bounded summary of a TASK gate subject."""
    description = safe_diagnostic(" ".join(task.description.split()))[:300]
    parts = [
        f"Task {task.id} (role {task.preferred_role.value}, plan v{task.plan_version})",
        f"description: {description}",
    ]
    if policy is None:
        parts.append("requirements preparation; no workspace execution policy yet")
    else:
        paths = ", ".join(safe_diagnostic(path) for path in policy.write_paths)
        commands = ", ".join(command.id for command in policy.commands) or "none"
        parts.extend(
            (
                f"write paths: {paths[:350]}",
                f"approved command IDs: {commands[:180]}",
            )
        )
    return safe_diagnostic("; ".join(parts))[:1000]


def save_initial_control_policy(
    uow: ProjectUnitOfWork,
    run: Run,
    mode: ControlMode,
    gates: frozenset[ApprovalStage] | None = None,
    *,
    at: datetime | None = None,
) -> ControlPolicy:
    """Save a run's immutable control mode inside its creation transaction.

    An ordinary autonomous run has no policy row or extra event; historical runs
    and existing event cursors keep the same default behavior.
    """
    if mode == ControlMode.AUTONOMOUS and gates:
        raise InputError("Autonomous mode cannot require approval gates")
    selected = (
        frozenset()
        if mode == ControlMode.AUTONOMOUS
        else SUPERVISED_GATES
        if gates is None
        else frozenset(gates)
    )
    policy = ControlPolicy(run_id=run.id, mode=mode, gates=selected)
    existing = uow.approvals.policy(run.id)
    if existing is not None:
        if existing == policy:
            return existing
        raise ConflictError("Run control policy is immutable")
    if run.plan_version != 0 or run.state not in {
        RunState.RECEIVED,
        RunState.CONTEXT_SYNC,
        RunState.ANALYZING,
        RunState.GOAL_DEFINED,
    }:
        raise ConflictError("Set run control mode before execution starts")
    if uow.approvals.list(run.id):
        raise ConflictError("Control policy cannot change after an approval was requested")
    if mode == ControlMode.AUTONOMOUS:
        return policy
    uow.approvals.save_policy(policy)
    at = at or utc_now()
    emit(
        uow,
        run,
        EventType.CONTROL_POLICY_CHANGED,
        "control:initial",
        at,
        EventPayload(
            status=mode,
            summary="Operator control policy configured",
            reason=",".join(sorted(stage.value for stage in selected)),
        ),
    )
    return policy


class ApprovalService:
    def __init__(self, unit_of_work: Callable[[], ProjectUnitOfWork]) -> None:
        self.unit_of_work = unit_of_work

    def policy(self, run_id: UUID) -> ControlPolicy:
        with self.unit_of_work() as uow:
            if uow.runs.get(run_id) is None:
                raise NotFoundError("Run not found")
            return uow.approvals.policy(run_id) or ControlPolicy(run_id=run_id)

    def configure(
        self,
        run_id: UUID,
        mode: ControlMode,
        gates: frozenset[ApprovalStage] | None = None,
    ) -> ControlPolicy:
        with self.unit_of_work() as uow:
            run = locked_run(uow, run_id)
            policy = save_initial_control_policy(uow, run, mode, gates)
            uow.commit()
            return policy

    def list(self, run_id: UUID) -> tuple[ApprovalRequest, ...]:
        with self.unit_of_work() as uow:
            if uow.runs.get(run_id) is None:
                raise NotFoundError("Run not found")
            return uow.approvals.list(run_id)

    def get(self, run_id: UUID, request_id: UUID) -> ApprovalRequest:
        with self.unit_of_work() as uow:
            request = uow.approvals.get(request_id)
            if request is None or request.run_id != run_id:
                raise NotFoundError("Approval request not found")
            return request

    @staticmethod
    def _validate_subject(
        run: Run, uow: ProjectUnitOfWork, stage: ApprovalStage, version: int
    ) -> None:
        if stage == ApprovalStage.GOAL:
            contract = (
                uow.runs.get_goal(run.current_goal_version_id)
                if run.current_goal_version_id
                else None
            )
            if contract is None or contract.goal.version != version:
                raise ConflictError("Goal version changed; refresh the approval subject")
        elif stage == ApprovalStage.TASK and version == 0 and run.state == RunState.ANALYZING:
            return
        elif version != run.plan_version or version <= 0:
            raise ConflictError("Plan version changed; refresh the approval subject")

    @staticmethod
    def _safe_fields(digest: str, reason: str) -> None:
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise InputError("Approval subject digest must be lowercase SHA-256 hex")
        if len(reason) > 1000 or safe_diagnostic(reason) != reason:
            raise PolicyDeniedError("Approval reason contains unsafe diagnostic content")

    def ensure(
        self,
        run_id: UUID,
        stage: ApprovalStage,
        subject_version: int,
        subject_digest: str,
        reason: str = "",
    ) -> ApprovalRequest | None:
        """Return the durable request, or None if this gate is disabled.

        Callers must stop unless the returned request is APPROVED. The method
        commits a new pending request before returning, so a worker can safely
        pause at the checkpoint and resume later.
        """
        self._safe_fields(subject_digest, reason)
        with self.unit_of_work() as uow:
            run = locked_run(uow, run_id)
            policy = uow.approvals.policy(run_id) or ControlPolicy(run_id=run_id)
            if not policy.requires(stage):
                return None
            self._validate_subject(run, uow, stage, subject_version)
            request_id = uuid5(run_id, f"approval:{stage}:{subject_version}:{subject_digest}")
            existing = uow.approvals.get(request_id)
            if existing:
                return existing
            request = ApprovalRequest(
                id=request_id,
                run_id=run_id,
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
            return request

    def decide(
        self,
        run_id: UUID,
        request_id: UUID,
        decision: ApprovalDecisionKind,
        actor: str,
        expected_subject_digest: str,
        reason: str = "",
    ) -> ApprovalRequest:
        """Append one operator decision; reject stale or altered subjects."""
        self._safe_fields(expected_subject_digest, reason)
        if decision == ApprovalDecisionKind.REJECT and not reason.strip():
            raise InputError("Rejecting an approval requires a reason")
        if not actor.strip() or len(actor) > 120 or safe_diagnostic(actor) != actor:
            raise InputError("Approval decision requires an operator identity")
        with self.unit_of_work() as uow:
            run = locked_run(uow, run_id)
            request = uow.approvals.get(request_id)
            if request is None or request.run_id != run_id:
                raise NotFoundError("Approval request not found")
            if request.subject_digest != expected_subject_digest:
                raise ConflictError("Approval subject changed; reload before deciding")
            self._validate_subject(run, uow, request.stage, request.subject_version)
            if request.decision:
                if request.decision.decision == decision and request.decision.actor == actor:
                    return request
                raise ConflictError("Approval request already has a different decision")
            recorded = ApprovalDecision(
                request_id=request_id,
                decision=decision,
                actor=actor,
                reason=reason,
            )
            uow.approvals.add_decision(recorded)
            status = (
                ApprovalStatus.APPROVED
                if decision == ApprovalDecisionKind.APPROVE
                else ApprovalStatus.REJECTED
            )
            emit(
                uow,
                run,
                EventType.APPROVAL_RECORDED,
                f"operator-approval:{request.id}:decided",
                recorded.created_at,
                EventPayload(
                    approval_request_id=request.id,
                    approval_stage=request.stage,
                    approval_subject_digest=request.subject_digest,
                    approval_actor=actor,
                    status=status,
                    reason=reason,
                ),
            )
            set_approval_actor_status(uow, run, request, status, recorded.created_at)
            uow.commit()
            return request.model_copy(update={"status": status, "decision": recorded})
