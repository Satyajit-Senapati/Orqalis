from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from orqalis.domain.artifact import Artifact, Finding
from orqalis.domain.delivery import ChangeReport, FinalValidation, GitDelivery
from orqalis.persistence.delivery_models import (
    ArtifactRow,
    FinalValidationRow,
    FindingRow,
    GitDeliveryRow,
    GuardianRow,
)


class SQLDeliveryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def guardians(self, run_id: UUID) -> tuple[ChangeReport, ...]:
        return tuple(
            ChangeReport.model_validate(row.payload)
            for row in self.session.scalars(
                select(GuardianRow)
                .where(GuardianRow.run_id == run_id)
                .order_by(GuardianRow.created_at, GuardianRow.id)
            )
        )

    def save_guardian(self, report: ChangeReport) -> None:
        self.session.add(
            GuardianRow(
                id=report.id,
                run_id=report.run_id,
                actor_session_id=report.actor_session_id,
                tree_hash=report.tree_hash,
                passed=report.passed,
                checkpoint=report.checkpoint,
                payload=report.model_dump(mode="json"),
                created_at=report.created_at,
            )
        )
        for finding in report.findings:
            self.save_finding(finding)
        self.session.flush()

    def validations(self, run_id: UUID) -> tuple[FinalValidation, ...]:
        return tuple(
            FinalValidation.model_validate(row, from_attributes=True)
            for row in self.session.scalars(
                select(FinalValidationRow)
                .where(FinalValidationRow.run_id == run_id)
                .order_by(FinalValidationRow.created_at, FinalValidationRow.id)
            )
        )

    def save_validation(self, validation: FinalValidation) -> None:
        self.session.add(
            FinalValidationRow(
                **validation.model_dump(exclude={"evidence_ids"}),
                evidence_ids=[str(ref) for ref in validation.evidence_ids],
            )
        )
        self.session.flush()

    def get(self, run_id: UUID) -> GitDelivery | None:
        row = self.session.scalar(select(GitDeliveryRow).where(GitDeliveryRow.run_id == run_id))
        return GitDelivery.model_validate(row, from_attributes=True) if row else None

    def save(self, delivery: GitDelivery) -> None:
        self.session.merge(
            GitDeliveryRow(
                **delivery.model_dump(exclude={"policy"}),
                policy=delivery.policy.model_dump(mode="json"),
            )
        )
        self.session.flush()

    def artifacts(self, run_id: UUID) -> tuple[Artifact, ...]:
        return tuple(
            Artifact.model_validate(row, from_attributes=True)
            for row in self.session.scalars(
                select(ArtifactRow)
                .where(ArtifactRow.run_id == run_id)
                .order_by(ArtifactRow.created_at)
            )
        )

    def save_artifact(self, artifact: Artifact) -> None:
        self.session.merge(ArtifactRow(**artifact.model_dump()))
        self.session.flush()

    def findings(self, run_id: UUID) -> tuple[Finding, ...]:
        return tuple(
            Finding.model_validate(row, from_attributes=True)
            for row in self.session.scalars(
                select(FindingRow)
                .where(FindingRow.run_id == run_id)
                .order_by(FindingRow.created_at)
            )
        )

    def save_finding(self, finding: Finding) -> None:
        self.session.merge(FindingRow(**finding.model_dump()))
        self.session.flush()
