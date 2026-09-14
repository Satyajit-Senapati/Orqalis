import asyncio
import hashlib
from collections.abc import Callable
from uuid import UUID, uuid5

from orqalis.core.approval_subjects import delivery_subject
from orqalis.core.approvals import ApprovalService
from orqalis.core.delivery_plan import DELIVERY_STEPS, delivery_plan
from orqalis.core.goals import GoalService
from orqalis.core.orchestrator import Orchestrator
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit, locked_run
from orqalis.delivery.commits import CommitService
from orqalis.delivery.documentation import DocumentationService
from orqalis.delivery.guardian import ChangeGuardian, GuardianService
from orqalis.delivery.validation import FinalValidationService
from orqalis.domain.approval import ApprovalStage, ApprovalStatus
from orqalis.domain.base import utc_now
from orqalis.domain.delivery import ChangeReport, DeliveryPolicy, DeliveryResult
from orqalis.domain.errors import ConflictError, NotFoundError, OrqalisError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.run import RunState
from orqalis.domain.task import TaskExecution, TaskStatus
from orqalis.execution.cancellation import watch_cancellation
from orqalis.git.service import LocalGitService
from orqalis.memory.curation import MemoryCurator
from orqalis.memory.service import MemoryService
from orqalis.observability.instrumentation import observed_async


class DeliveryCoordinator:
    """Application driver; only Orchestrator changes workflow and task states."""

    def __init__(
        self,
        factory: Callable[[], ProjectUnitOfWork],
        orchestrator: Orchestrator,
        goals: GoalService,
        git: LocalGitService,
        approvals: ApprovalService | None = None,
    ) -> None:
        self.factory, self.orchestrator, self.git = factory, orchestrator, git
        self.approvals = approvals or ApprovalService(factory)
        self.guardian = GuardianService(factory, ChangeGuardian(git))
        self.documentation = DocumentationService(factory)
        self.validation = FinalValidationService(factory, goals, git)
        self.commits = CommitService(factory, git)
        self.curator = MemoryCurator(factory, MemoryService(factory, git), git)

    @observed_async("delivery.finalize")
    async def finalize(self, run_id: UUID, policy: DeliveryPolicy) -> DeliveryResult:
        with self.factory() as lease:
            if not lease.execution.try_run_lock(run_id):
                raise ConflictError("Another Orchestrator worker owns this run")
            return await watch_cancellation(self.factory, run_id, self._finalize(run_id, policy))

    async def _finalize(self, run_id: UUID, policy: DeliveryPolicy) -> DeliveryResult:
        requested = None
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            if run.state not in {
                RunState.REVIEWING,
                RunState.CHANGE_GUARD,
                RunState.DOCUMENTING,
                RunState.DELIVERY_VALIDATION,
                RunState.COMMITTING,
                RunState.PUSHING,
                RunState.MEMORY_FINALIZATION,
                RunState.COMPLETED,
            }:
                raise ConflictError("Run is not at a delivery checkpoint")
            fingerprint = hashlib.sha256(policy.model_dump_json().encode()).hexdigest()
            bound = uow.events.by_key(run_id, "delivery:policy")
            if bound and bound.payload.summary != fingerprint:
                raise ConflictError("Delivery policy differs from its persisted authorization")
            if not bound:
                reviews = uow.execution.reviews(run_id)
                review = reviews[-1] if reviews else None
                if review is None or review.result.overall != "PASS":
                    raise ConflictError("Delivery approval requires a passing persisted review")
        if not bound:
            if review is None:
                raise ConflictError("Passing review missing")
            requested = self.approvals.ensure(
                run_id,
                ApprovalStage.DELIVERY,
                run.plan_version,
                delivery_subject(run, review, policy),
                (
                    f"Review tree {review.tree_hash[:16]}, push={policy.push}, "
                    f"remote={policy.remote}, docs={policy.documentation_path or 'none'}, "
                    f"sensitive paths={len(policy.approved_sensitive_paths)}. "
                    "Inspect the delivery policy and repository diff before approval."
                ),
            )
            if requested is not None and requested.status != ApprovalStatus.APPROVED:
                raise PolicyDeniedError(f"Delivery approval required: {requested.id}")
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            bound = uow.events.by_key(run_id, "delivery:policy")
            if not bound:
                emit(
                    uow,
                    run,
                    EventType.APPROVAL_RECORDED,
                    "delivery:policy",
                    utc_now(),
                    EventPayload(
                        summary=fingerprint,
                        reason="Explicit delivery policy",
                        approval_request_id=requested.id if requested else None,
                        approval_subject_digest=requested.subject_digest if requested else None,
                    ),
                )
                uow.commit()
            plan = uow.runtime.get_plan(run_id, run.plan_version)
            if plan is None:
                raise NotFoundError("Accepted plan missing")
        if not any(t.id == uuid5(run_id, "delivery-task:git") for t in plan.tasks):
            self.orchestrator.install_delivery_plan(delivery_plan(plan), "delivery:plan")
        for step, _, _ in DELIVERY_STEPS:
            with self.factory() as uow:
                run = locked_run(uow, run_id)
                plan = uow.runtime.get_plan(run_id, run.plan_version)
                assert plan is not None
                task = next(t for t in plan.tasks if t.id == uuid5(run_id, f"delivery-task:{step}"))
                if task.status == TaskStatus.SUCCEEDED:
                    continue
                if task.status not in {TaskStatus.READY, TaskStatus.RUNNING}:
                    raise ConflictError("Delivery task requires an explicit recovery checkpoint")
            target = {
                "implementation": RunState.CHANGE_GUARD,
                "documentation": RunState.DOCUMENTING,
                "validation": RunState.DELIVERY_VALIDATION,
                "final": RunState.DELIVERY_VALIDATION,
                "git": RunState.COMMITTING,
                "memory": RunState.MEMORY_FINALIZATION,
            }[step]
            if run.state != target and not (step == "git" and run.state == RunState.PUSHING):
                self.orchestrator.advance(run_id, target, f"delivery:state:{target}")
            with self.factory() as uow:
                attempts = uow.runtime.executions(run_id)
            attempt = next(
                (a for a in attempts if a.task_id == task.id and a.status == TaskStatus.RUNNING),
                None,
            ) or self.orchestrator.start_task(
                run_id, task.id, f"delivery:start:{step}:attempt:{task.attempt_count + 1}"
            )
            try:
                if step in {"implementation", "final"}:
                    report = self.guardian.inspect(
                        run_id, attempt.assigned_actor_session_id, policy, step
                    )
                    self._check_report(run_id, report, policy)
                elif step == "documentation":
                    with self.factory() as uow:
                        accepted = [
                            r
                            for r in uow.delivery.guardians(run_id)
                            if r.checkpoint == "implementation"
                        ][-1]
                    self.documentation.write(
                        run_id, attempt.assigned_actor_session_id, accepted, policy
                    )
                elif step == "validation":
                    if not (await self.validation.validate(run_id, attempt)).passed:
                        raise PolicyDeniedError("Final validation failed")
                elif step == "memory":
                    self.curator.promote(run_id, attempt.assigned_actor_session_id)
                elif step == "git":
                    await self._git(run_id, attempt, policy)
                self.orchestrator.transition_task(
                    run_id, attempt.id, TaskStatus.SUCCEEDED, f"delivery:done:{step}:{attempt.id}"
                )
            except (OrqalisError, asyncio.CancelledError):
                with self.factory() as uow:
                    interrupted = locked_run(uow, run_id)
                if interrupted.state in {RunState.CANCELLED, RunState.FAILED, RunState.COMPLETED}:
                    raise
                self.orchestrator.transition_task(
                    run_id, attempt.id, TaskStatus.BLOCKED, f"delivery:blocked:{attempt.id}"
                )
                self.orchestrator.advance(
                    run_id, RunState.BLOCKED, f"delivery:blocked:{attempt.id}"
                )
                raise
        with self.factory() as uow:
            run = locked_run(uow, run_id)
        if run.state == RunState.MEMORY_FINALIZATION:
            self.orchestrator.advance(run_id, RunState.COMPLETED, "delivery:completed")
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            delivery = uow.delivery.get(run_id)
            final = [r for r in uow.delivery.guardians(run_id) if r.checkpoint == "final"][-1]
            assert delivery is not None
            return DeliveryResult(
                run_id=run_id,
                state=run.state,
                commit_sha=delivery.commit_sha,
                pushed=delivery.push_status == "pushed",
                changed_paths=tuple(c.path for c in final.changes),
            )

    def _check_report(self, run_id: UUID, report: ChangeReport, policy: DeliveryPolicy) -> None:
        if not report.passed:
            raise PolicyDeniedError("Change Guardian rejected delivery; inspect persisted findings")
        with self.factory() as uow:
            if report.checkpoint == "implementation":
                if report.tree_hash != uow.execution.reviews(run_id)[-1].tree_hash:
                    raise PolicyDeniedError("Implementation changed since independent review")
            else:
                accepted = [
                    r for r in uow.delivery.guardians(run_id) if r.checkpoint == "implementation"
                ][-1]
                old = {c.path: c.new_hash for c in accepted.changes}
                new = {c.path: c.new_hash for c in report.changes}
                for path in old.keys() | new.keys():
                    if path != policy.documentation_path and old.get(path) != new.get(path):
                        raise PolicyDeniedError("Non-documentation changes followed acceptance")
                validations = uow.delivery.validations(run_id)
                if not validations or validations[-1].tree_hash != report.tree_hash:
                    raise PolicyDeniedError("Final tree changed after validation")

    async def _git(self, run_id: UUID, attempt: TaskExecution, policy: DeliveryPolicy) -> None:
        with self.factory() as uow:
            run = locked_run(uow, run_id)
        if run.state == RunState.COMMITTING:
            self.commits.commit(run_id, policy, attempt.assigned_actor_session_id)
        if policy.push:
            if run.state != RunState.PUSHING:
                self.orchestrator.advance(run_id, RunState.PUSHING, "delivery:state:PUSHING")
            self.commits.push(run_id, attempt.assigned_actor_session_id)
