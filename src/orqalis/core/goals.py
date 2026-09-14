from collections.abc import Callable
from uuid import UUID, uuid5

from orqalis.core.approvals import save_initial_control_policy
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit, orchestrator_actor
from orqalis.domain.acceptance import (
    AcceptanceCriterion,
    AcceptanceStatus,
    CriterionDefinition,
    GoalContract,
    GoalDraft,
    GoalVersion,
)
from orqalis.domain.agent import AgentRole
from orqalis.domain.approval import ApprovalStage, ControlMode
from orqalis.domain.artifact import Evidence, ValidationObservation
from orqalis.domain.base import utc_now
from orqalis.domain.errors import (
    ConflictError,
    InputError,
    NotFoundError,
    OrqalisError,
    PolicyDeniedError,
)
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.project import Project
from orqalis.domain.provider import InvocationStatus
from orqalis.domain.run import Run, RunState
from orqalis.domain.task import TaskStatus
from orqalis.evaluation.ports import Evaluator
from orqalis.security.redaction import safe_diagnostic


class GoalService:
    """Versioned goal/acceptance operations; lifecycle transitions belong to Orchestrator."""

    def __init__(self, unit_of_work: Callable[[], ProjectUnitOfWork]) -> None:
        self.unit_of_work = unit_of_work

    def _contract(
        self,
        run_id: UUID,
        draft: GoalDraft,
        version: int,
        supersedes: UUID | None = None,
        reason: str | None = None,
    ) -> GoalContract:
        payload = draft.model_dump_json()
        if safe_diagnostic(payload) != payload or any(
            marker in payload.lower() for marker in ("chain_of_thought", "<thinking>", "<analysis>")
        ):
            raise PolicyDeniedError("Goals cannot contain credentials or private reasoning")
        goal = GoalVersion(
            run_id=run_id,
            version=version,
            **draft.model_dump(exclude={"criteria"}),
            supersedes_goal_version_id=supersedes,
            revision_reason=reason,
        )
        criteria = tuple(
            AcceptanceCriterion(goal_version_id=goal.id, **item.model_dump())
            for item in draft.criteria
        )
        return GoalContract(goal=goal, criteria=criteria)

    def create(
        self,
        project: Project,
        request: str,
        branch: str,
        base: str,
        draft: GoalDraft,
        mode: ControlMode = ControlMode.AUTONOMOUS,
        gates: frozenset[ApprovalStage] | None = None,
    ) -> tuple[Run, GoalContract]:
        if safe_diagnostic(request) != request:
            raise PolicyDeniedError("Run requests cannot contain credentials")
        run = Run(
            project_id=project.id,
            request=request,
            target_branch=branch,
            base_commit=base,
            max_repair_iterations=project.settings.max_repair_iterations,
        )
        contract = self._contract(run.id, draft, 1)
        with self.unit_of_work() as uow:
            uow.runs.add(run)
            uow.runs.save_goal(contract)
            uow.runs.set_current_goal(run.id, contract.goal.id)
            emit(
                uow,
                run,
                EventType.RUN_CREATED,
                "run:created",
                run.created_at,
                EventPayload(status=run.state),
            )
            orchestrator_actor(uow, run, run.created_at)
            save_initial_control_policy(uow, run, mode, gates, at=run.created_at)
            emit(
                uow,
                run,
                EventType.GOAL_VERSION_CREATED,
                "goal:1",
                run.created_at,
                EventPayload(goal_version_id=contract.goal.id),
            )
            for criterion in contract.criteria:
                emit(
                    uow,
                    run,
                    EventType.ACCEPTANCE_CREATED,
                    f"criterion:{criterion.id}",
                    run.created_at,
                    EventPayload(criterion_id=criterion.id, status=criterion.status),
                )
            uow.commit()
            persisted = uow.runs.get(run.id)
            if persisted:
                run = persisted
        return run.model_copy(update={"current_goal_version_id": contract.goal.id}), contract

    def create_pending(
        self,
        project: Project,
        request: str,
        branch: str,
        base: str,
        mode: ControlMode = ControlMode.AUTONOMOUS,
        gates: frozenset[ApprovalStage] | None = None,
    ) -> Run:
        if safe_diagnostic(request) != request:
            raise PolicyDeniedError("Run requests cannot contain credentials")
        run = Run(
            project_id=project.id,
            request=request,
            target_branch=branch,
            base_commit=base,
            max_repair_iterations=project.settings.max_repair_iterations,
        )
        with self.unit_of_work() as uow:
            uow.runs.add(run)
            emit(
                uow,
                run,
                EventType.RUN_CREATED,
                "run:created",
                run.created_at,
                EventPayload(status=run.state),
            )
            orchestrator_actor(uow, run, run.created_at)
            save_initial_control_policy(uow, run, mode, gates, at=run.created_at)
            uow.commit()
        return run

    def define_initial(self, run_id: UUID, execution_id: UUID, draft: GoalDraft) -> GoalContract:
        with self.unit_of_work() as uow:
            run = uow.runs.get(run_id, for_update=True)
            if run is None or run.state != RunState.ANALYZING:
                raise ConflictError("Initial requirements need the analyzing checkpoint")
            if run.current_goal_version_id:
                existing = uow.runs.get_goal(run.current_goal_version_id)
                assert existing is not None
                saved = GoalDraft(
                    **{
                        key: getattr(existing.goal, key)
                        for key in GoalDraft.model_fields
                        if key != "criteria"
                    },
                    criteria=tuple(
                        CriterionDefinition(
                            **{key: getattr(c, key) for key in CriterionDefinition.model_fields}
                        )
                        for c in existing.criteria
                    ),
                )
                if saved != draft:
                    raise ConflictError("Initial goal is already defined; use an explicit revision")
                return existing
            attempt = next(
                (a for a in uow.runtime.executions(run_id) if a.id == execution_id), None
            )
            actor = next(
                (
                    a
                    for a in uow.runtime.actors(run_id)
                    if attempt and a.id == attempt.assigned_actor_session_id
                ),
                None,
            )
            if (
                not attempt
                or attempt.status != TaskStatus.RUNNING
                or not actor
                or actor.role != AgentRole.REQUIREMENTS
            ):
                raise PolicyDeniedError("Initial requirements need an active Requirements actor")
            if not any(
                p.task_execution_id == attempt.id
                and p.status == InvocationStatus.SUCCEEDED
                and p.result
                and p.result.output == draft.model_dump(mode="json")
                for p in uow.providers.list(run_id)
            ):
                raise PolicyDeniedError(
                    "Goal proposal does not match the persisted Requirements result"
                )
            contract = self._contract(run_id, draft, 1)
            uow.runs.save_goal(contract)
            uow.runs.set_current_goal(run_id, contract.goal.id)
            at = utc_now()
            emit(
                uow,
                run,
                EventType.GOAL_VERSION_CREATED,
                "goal:1",
                at,
                EventPayload(goal_version_id=contract.goal.id),
                actor.id,
                attempt.task_id,
                attempt.id,
            )
            for criterion in contract.criteria:
                emit(
                    uow,
                    run,
                    EventType.ACCEPTANCE_CREATED,
                    f"criterion:{criterion.id}",
                    at,
                    EventPayload(criterion_id=criterion.id, status=criterion.status),
                    actor.id,
                    attempt.task_id,
                    attempt.id,
                )
            uow.commit()
            return contract

    def get(self, run_id: UUID) -> GoalContract:
        with self.unit_of_work() as uow:
            run = uow.runs.get(run_id)
            if not run or not run.current_goal_version_id:
                raise NotFoundError("Run or current goal not found")
            contract = uow.runs.get_goal(run.current_goal_version_id)
            if contract is None:
                raise NotFoundError("Current goal not found")
            return contract

    def revise(
        self, run_id: UUID, draft: GoalDraft, reason: str, expected_version: int
    ) -> GoalContract:
        if not reason.strip() or safe_diagnostic(reason) != reason:
            raise InputError("A non-secret revision reason is required")
        with self.unit_of_work() as uow:
            run = uow.runs.get(run_id, for_update=True)
            if not run or not run.current_goal_version_id:
                raise NotFoundError("Run or current goal not found")
            if run.state not in {
                RunState.RECEIVED,
                RunState.ANALYZING,
                RunState.GOAL_DEFINED,
                RunState.PAUSED,
                RunState.HUMAN_REVIEW_REQUIRED,
            }:
                raise ConflictError("Pause execution before explicitly revising the goal")
            if uow.events.by_key(run.id, "delivery:policy"):
                raise PolicyDeniedError("Delivery has started; a changed goal requires a new run")
            current = uow.runs.get_goal(run.current_goal_version_id)
            if not current or current.goal.version != expected_version:
                raise ConflictError("Goal version changed; reload before revising")
            revised = self._contract(run_id, draft, expected_version + 1, current.goal.id, reason)
            uow.runs.save_goal(revised)
            uow.runs.set_current_goal(run_id, revised.goal.id)
            emit(
                uow,
                run,
                EventType.GOAL_VERSION_CREATED,
                f"goal:{revised.goal.version}",
                utc_now(),
                EventPayload(goal_version_id=revised.goal.id, reason=reason),
            )
            for criterion in revised.criteria:
                emit(
                    uow,
                    run,
                    EventType.ACCEPTANCE_CREATED,
                    f"criterion:{criterion.id}",
                    utc_now(),
                    EventPayload(criterion_id=criterion.id, status=criterion.status),
                )
            uow.commit()
            return revised

    def validate(
        self,
        run_id: UUID,
        criterion_key: str,
        evaluator: Evaluator,
        idempotency_key: str,
        execution_id: UUID | None = None,
    ) -> Evidence:
        if not idempotency_key.strip():
            raise InputError("Validation requires an idempotency key")
        with self.unit_of_work() as uow:
            run = uow.runs.get(run_id, for_update=True)
            if not run or not run.current_goal_version_id:
                raise NotFoundError("Run or current goal not found")
            contract = uow.runs.get_goal(run.current_goal_version_id)
            if not contract:
                raise NotFoundError("Current goal not found")
            criterion = next(
                (item for item in contract.criteria if item.key == criterion_key), None
            )
            if criterion is None:
                raise NotFoundError("Criterion not found")
            evidence_id = uuid5(criterion.id, idempotency_key)
            existing = uow.runs.get_evidence(evidence_id)
            if existing:
                return existing
            if uow.events.by_key(run_id, f"validation:{evidence_id}:start"):
                raise ConflictError("Validation is active or interrupted; inspect before retrying")
            attempt = (
                next(
                    (item for item in uow.runtime.executions(run_id) if item.id == execution_id),
                    None,
                )
                if execution_id
                else None
            )
            if execution_id and (attempt is None or attempt.status != TaskStatus.RUNNING):
                raise ConflictError("Validation requires an active task attempt")
            actor_id = attempt.assigned_actor_session_id if attempt else None
            task_id = attempt.task_id if attempt else None
            uow.runs.save_criterion(
                criterion.model_copy(update={"status": AcceptanceStatus.TESTING})
            )
            emit(
                uow,
                run,
                EventType.TEST_STARTED,
                f"validation:{evidence_id}:start",
                utc_now(),
                EventPayload(criterion_id=criterion.id, status=AcceptanceStatus.TESTING),
                actor_id,
                task_id,
                execution_id,
            )
            uow.commit()
        failure: OrqalisError | None = None
        try:
            observation = evaluator.evaluate(criterion.validation_spec)
            if observation.validator_type != criterion.validation_spec.kind:
                raise ConflictError("Evaluator observation does not match the criterion validator")
            if safe_diagnostic(observation.model_dump_json()) != observation.model_dump_json():
                raise PolicyDeniedError("Validator emitted unsafe diagnostic content")
        except OrqalisError as error:
            failure = error
            observation = ValidationObservation(
                validator_type=criterion.validation_spec.kind,
                passed=False,
                error_code=error.code,
                duration_ms=0,
            )
        with self.unit_of_work() as uow:
            current = uow.runs.get(run_id, for_update=True)
            if current is None or current.current_goal_version_id != criterion.goal_version_id:
                raise ConflictError("Goal changed during validation; evidence cannot be promoted")
            latest = uow.runs.get_goal(current.current_goal_version_id)
            assert latest is not None
            current_criterion = next(item for item in latest.criteria if item.id == criterion.id)
            status = AcceptanceStatus.PASS if observation.passed else AcceptanceStatus.FAIL
            if criterion.validation_spec.kind in {"review", "manual"}:
                status = AcceptanceStatus.PENDING
            if current.state in {RunState.CANCELLED, RunState.FAILED}:
                status = AcceptanceStatus.PENDING
            evidence = Evidence(
                id=evidence_id,
                run_id=run_id,
                criterion_id=criterion.id,
                task_id=task_id,
                task_execution_id=execution_id,
                evidence_type=criterion.validation_spec.kind,
                structured_data=observation,
            )
            updated = AcceptanceCriterion.model_validate(
                {
                    **current_criterion.model_dump(),
                    "status": status,
                    "attempt_count": current_criterion.attempt_count + 1,
                    "last_validated_at": utc_now(),
                    "evidence_refs": (*current_criterion.evidence_refs, evidence.id),
                }
            )
            uow.runs.save_evaluation(updated, evidence)
            payload = EventPayload(
                criterion_id=criterion.id, status=status, evidence_ids=(evidence.id,)
            )
            emit(
                uow,
                current,
                EventType.EVIDENCE_RECORDED,
                f"evidence:{evidence.id}",
                evidence.created_at,
                payload,
                actor_id,
                task_id,
                execution_id,
            )
            emit(
                uow,
                current,
                EventType.TEST_COMPLETED,
                f"validation:{evidence_id}:end",
                evidence.created_at,
                payload,
                actor_id,
                task_id,
                execution_id,
            )
            if status in {AcceptanceStatus.PASS, AcceptanceStatus.FAIL}:
                emit(
                    uow,
                    current,
                    EventType.CRITERION_PASSED
                    if status == AcceptanceStatus.PASS
                    else EventType.CRITERION_FAILED,
                    f"criterion-result:{evidence.id}",
                    evidence.created_at,
                    payload,
                    actor_id,
                    task_id,
                    execution_id,
                )
            uow.commit()
        if failure:
            raise failure
        return evidence
