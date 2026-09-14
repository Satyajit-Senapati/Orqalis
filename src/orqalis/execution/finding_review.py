"""Independent, evidence-backed disposition of untrusted worker findings."""

from uuid import UUID

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit
from orqalis.domain.acceptance import FileValidation, GoalContract
from orqalis.domain.base import utc_now
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.execution import ReviewResult
from orqalis.domain.run import Run
from orqalis.evaluation.validators import LocalEvaluator
from orqalis.execution.filesystem import ScopedFilesystem


def review_external_findings(
    uow: ProjectUnitOfWork,
    run: Run,
    actor_id: UUID,
    review_id: UUID,
    result: ReviewResult,
    goal: GoalContract,
    files: ScopedFilesystem,
) -> bool:
    """Return whether blocking observations remain; caller verifies Reviewer authority."""
    findings = {
        finding.id: finding
        for finding in uow.delivery.findings(run.id)
        if finding.category == "external_worker" and finding.status == "open"
    }
    if {review.finding_id for review in result.finding_reviews} != set(findings) or len(
        result.finding_reviews
    ) != len(findings):
        raise ConflictError("Reviewer must evaluate each open worker finding exactly once")
    unresolved = False
    for review in result.finding_reviews:
        finding = findings[review.finding_id]
        if not review.reason.strip():
            raise ConflictError("Finding disposition requires an actionable reason")
        if not review.resolved:
            unresolved |= finding.severity == "blocking"
            continue
        if not review.evidence_refs and not review.source_checks:
            raise PolicyDeniedError("Finding resolution requires verifiable evidence")
        verified_source_evidence = False
        for reference in review.evidence_refs:
            evidence = uow.runs.get_evidence(reference)
            criterion = next(
                (c for c in goal.criteria if evidence and c.id == evidence.criterion_id), None
            )
            if (
                evidence is None
                or evidence.run_id != run.id
                or evidence.status != "valid"
                or not evidence.structured_data.passed
                or evidence.created_at < finding.created_at
                or criterion is None
                or not criterion.evidence_refs
                or criterion.evidence_refs[-1] != reference
                or (
                    finding.criterion_id is not None
                    and evidence.criterion_id != finding.criterion_id
                )
            ):
                raise PolicyDeniedError("Finding resolution references stale or unrelated evidence")
            if (
                finding.source_ref
                and isinstance(criterion.validation_spec, FileValidation)
                and criterion.validation_spec.path == finding.source_ref
                and evidence.structured_data.source_ref == finding.source_ref
            ):
                if not LocalEvaluator(files.root).evaluate(criterion.validation_spec).passed:
                    raise ConflictError("Finding source changed since its validation evidence")
                verified_source_evidence = True
        if (
            finding.source_ref
            and not verified_source_evidence
            and not any(check.path == finding.source_ref for check in review.source_checks)
        ):
            raise PolicyDeniedError("Finding resolution must inspect its reported source")
        for check in review.source_checks:
            if check.contains not in files.read(check.path):
                raise ConflictError("Finding resolution source assertion is not present")
        uow.delivery.save_finding(finding.model_copy(update={"status": "resolved"}))
        emit(
            uow,
            run,
            EventType.FINDING_RESOLVED,
            f"review:{review_id}:finding:{finding.id}",
            utc_now(),
            EventPayload(
                summary=review.reason,
                review_id=review_id,
                finding_ids=(finding.id,),
                evidence_ids=review.evidence_refs,
                status="resolved",
            ),
            actor_id,
            finding.task_id,
        )
    if unresolved and not result.blocking_findings:
        raise ConflictError("Unresolved blocking findings require actionable review findings")
    return unresolved
