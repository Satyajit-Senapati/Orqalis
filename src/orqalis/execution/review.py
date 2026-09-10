import hashlib
from collections.abc import Callable
from uuid import UUID, uuid5

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit, locked_run
from orqalis.domain.acceptance import AcceptanceCriterion, AcceptanceStatus, ReviewValidation
from orqalis.domain.agent import ActorStatus, AgentRole
from orqalis.domain.artifact import Evidence, ValidationObservation
from orqalis.domain.base import utc_now
from orqalis.domain.errors import ConflictError, NotFoundError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.execution import ReviewRecord, ReviewResult, RunWorkspace
from orqalis.domain.run import RunState
from orqalis.execution.filesystem import ScopedFilesystem
from orqalis.execution.workspaces import verify_workspace
from orqalis.git.service import LocalGitService
from orqalis.providers.validation import safe_value


def workspace_digest(workspace: RunWorkspace, git: LocalGitService) -> str:
    verify_workspace(workspace, git)
    digest = hashlib.sha256(workspace.base_commit.encode())
    files = ScopedFilesystem(workspace.path, workspace.policy)
    for path in git.status(workspace.path).changed_paths:
        target = files.target(path)
        digest.update(path.encode())
        digest.update(b"\0")
        if target.exists():
            if not target.is_file() or target.stat().st_size > 10_000_000:
                raise PolicyDeniedError("Changed artifact exceeds review limits")
            digest.update(hashlib.sha256(target.read_bytes()).digest())
        else:
            digest.update(b"deleted")
    return digest.hexdigest()


class ReviewService:
    def __init__(self, factory: Callable[[], ProjectUnitOfWork], git: LocalGitService) -> None:
        self.factory, self.git = factory, git

    def record(self, run_id: UUID, actor_id: UUID, result: ReviewResult, key: str) -> ReviewRecord:
        safe_value(result.model_dump(mode="json"))
        review_id = uuid5(run_id, f"review:{key}")
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            previous = next(
                (record for record in uow.execution.reviews(run_id) if record.id == review_id), None
            )
            if previous:
                if previous.result != result or previous.actor_session_id != actor_id:
                    raise ConflictError("Review key belongs to another result")
                return previous
            actor = next((item for item in uow.runtime.actors(run_id) if item.id == actor_id), None)
            if run.state != RunState.REVIEWING or actor is None or actor.role != AgentRole.REVIEWER:
                raise PolicyDeniedError(
                    "Only the assigned Reviewer can record an acceptance review"
                )
            if actor.status != ActorStatus.WORKING or actor.current_task_id is None:
                raise PolicyDeniedError("Reviewer session must be active")
            if not any(
                item.actor_session_id == actor_id
                and item.result is not None
                and item.result.output == result.model_dump(mode="json")
                for item in uow.providers.list(run_id)
            ):
                raise PolicyDeniedError("Review must match a persisted result of this Reviewer")
            goal = (
                uow.runs.get_goal(run.current_goal_version_id)
                if run.current_goal_version_id
                else None
            )
            workspace = uow.execution.workspace(run_id)
            if goal is None or workspace is None:
                raise NotFoundError("Review contract or workspace missing")
            if {item.criterion_id for item in result.criteria} != {
                item.id for item in goal.criteria
            } or (len(result.criteria) != len(goal.criteria)):
                raise ConflictError("Reviewer must evaluate every current criterion exactly once")
            expected_pass = not result.blocking_findings and all(
                review.status == "PASS"
                for review in result.criteria
                if next(c for c in goal.criteria if c.id == review.criterion_id).priority
                == "required"
            )
            if (result.overall == "PASS") != expected_pass:
                raise ConflictError("Review overall outcome contradicts its criteria/findings")
            files = ScopedFilesystem(workspace.path, workspace.policy)
            for item in result.criteria:
                criterion = next(c for c in goal.criteria if c.id == item.criterion_id)
                evidence = [uow.runs.get_evidence(ref) for ref in item.evidence_refs]
                if any(
                    e is None
                    or e.run_id != run_id
                    or e.criterion_id != criterion.id
                    or e.status != "valid"
                    for e in evidence
                ):
                    raise PolicyDeniedError("Reviewer references invalid or unrelated evidence")
                if item.status == "PASS":
                    if isinstance(criterion.validation_spec, ReviewValidation):
                        if criterion.validation_spec.kind == "manual" or not item.source_checks:
                            raise PolicyDeniedError(
                                "Review PASS requires verifiable source references"
                            )
                        digests = []
                        for check in item.source_checks:
                            target = files.target(check.path)
                            content = files.read(check.path)
                            if check.contains not in content:
                                raise ConflictError("Reviewer source assertion is not present")
                            digests.append(hashlib.sha256(target.read_bytes()).hexdigest())
                        observed = ValidationObservation(
                            validator_type="review",
                            passed=True,
                            output=item.reason,
                            source_ref=";".join(check.path for check in item.source_checks),
                            content_hash=hashlib.sha256("".join(digests).encode()).hexdigest(),
                            duration_ms=0,
                        )
                        proof = Evidence(
                            id=uuid5(review_id, str(criterion.id)),
                            run_id=run_id,
                            criterion_id=criterion.id,
                            evidence_type="review",
                            structured_data=observed,
                        )
                        updated = AcceptanceCriterion.model_validate(
                            {
                                **criterion.model_dump(),
                                "status": AcceptanceStatus.PASS,
                                "last_validated_at": utc_now(),
                                "attempt_count": criterion.attempt_count + 1,
                                "evidence_refs": (*criterion.evidence_refs, proof.id),
                            }
                        )
                        uow.runs.save_evaluation(updated, proof)
                        emit(
                            uow,
                            run,
                            EventType.EVIDENCE_RECORDED,
                            f"review:{proof.id}",
                            utc_now(),
                            EventPayload(criterion_id=criterion.id, evidence_ids=(proof.id,)),
                            actor_id,
                        )
                        emit(
                            uow,
                            run,
                            EventType.CRITERION_PASSED,
                            f"review:pass:{proof.id}",
                            utc_now(),
                            EventPayload(
                                criterion_id=criterion.id, status="PASS", evidence_ids=(proof.id,)
                            ),
                            actor_id,
                        )
                    elif (
                        criterion.status != AcceptanceStatus.PASS
                        or not evidence
                        or criterion.evidence_refs[-1] not in item.evidence_refs
                        or not all(e and e.structured_data.passed for e in evidence)
                    ):
                        raise PolicyDeniedError(
                            "Deterministic criterion lacks current passing evidence"
                        )
                else:
                    if not item.reason.strip():
                        raise ConflictError("Failed review criteria require an actionable reason")
                    proof = Evidence(
                        id=uuid5(review_id, str(criterion.id)),
                        run_id=run_id,
                        criterion_id=criterion.id,
                        evidence_type="review",
                        structured_data=ValidationObservation(
                            validator_type="review",
                            passed=False,
                            output=item.reason,
                            duration_ms=0,
                        ),
                    )
                    updated = AcceptanceCriterion.model_validate(
                        {
                            **criterion.model_dump(),
                            "status": AcceptanceStatus.FAIL,
                            "last_validated_at": utc_now(),
                            "attempt_count": criterion.attempt_count + 1,
                            "evidence_refs": (*criterion.evidence_refs, proof.id),
                        }
                    )
                    uow.runs.save_evaluation(updated, proof)
                    emit(
                        uow,
                        run,
                        EventType.CRITERION_FAILED,
                        f"review:fail:{proof.id}",
                        utc_now(),
                        EventPayload(
                            criterion_id=criterion.id, status="FAIL", evidence_ids=(proof.id,)
                        ),
                        actor_id,
                    )
            record = ReviewRecord(
                id=review_id,
                run_id=run_id,
                goal_version_id=goal.goal.id,
                plan_version=run.plan_version,
                actor_session_id=actor_id,
                tree_hash=workspace_digest(workspace, self.git),
                result=result,
            )
            uow.execution.save_review(record)
            emit(
                uow,
                run,
                EventType.REVIEW_COMPLETED,
                f"review:{review_id}:completed",
                utc_now(),
                EventPayload(review_id=record.id, status=result.overall),
                actor_id,
            )
            uow.commit()
            return record
