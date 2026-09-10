from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from orqalis.domain.acceptance import AcceptanceCriterion, GoalContract, GoalVersion
from orqalis.domain.artifact import Evidence
from orqalis.domain.run import Run
from orqalis.persistence.workflow_models import CriterionRow, EvidenceRow, GoalRow, RunRow


class SQLRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, run: Run) -> None:
        self.session.add(RunRow(**run.model_dump()))
        self.session.flush()

    def get(self, run_id: UUID, for_update: bool = False) -> Run | None:
        query = select(RunRow).where(RunRow.id == run_id)
        if for_update:
            query = query.with_for_update()
        row = self.session.scalar(query)
        return Run.model_validate(row, from_attributes=True) if row else None

    def list(self, project_id: UUID | None = None, limit: int = 100) -> tuple[Run, ...]:
        query = select(RunRow).order_by(RunRow.created_at.desc(), RunRow.id).limit(limit)
        if project_id:
            query = query.where(RunRow.project_id == project_id)
        return tuple(
            Run.model_validate(row, from_attributes=True) for row in self.session.scalars(query)
        )

    def save(self, run: Run) -> None:
        self.session.execute(
            update(RunRow)
            .where(RunRow.id == run.id)
            .values(**run.model_dump(exclude={"id", "created_at", "last_event_sequence"}))
        )

    def save_goal(self, contract: GoalContract) -> None:
        self.session.add(GoalRow(**contract.goal.model_dump()))
        self.session.flush()
        for criterion in contract.criteria:
            values = criterion.model_dump(exclude={"validation_spec", "evidence_refs"})
            self.session.add(
                CriterionRow(
                    **values,
                    validation_spec=criterion.validation_spec.model_dump(mode="json"),
                    evidence_refs=[str(ref) for ref in criterion.evidence_refs],
                )
            )
        self.session.flush()

    def set_current_goal(self, run_id: UUID, goal_id: UUID) -> None:
        self.session.execute(
            update(RunRow).where(RunRow.id == run_id).values(current_goal_version_id=goal_id)
        )

    def get_goal(self, goal_id: UUID) -> GoalContract | None:
        row = self.session.get(GoalRow, goal_id)
        if row is None:
            return None
        criteria = tuple(
            AcceptanceCriterion.model_validate(item, from_attributes=True)
            for item in self.session.scalars(
                select(CriterionRow)
                .where(CriterionRow.goal_version_id == goal_id)
                .order_by(CriterionRow.key)
            )
        )
        return GoalContract(
            goal=GoalVersion.model_validate(row, from_attributes=True), criteria=criteria
        )

    def get_evidence(self, evidence_id: UUID) -> Evidence | None:
        row = self.session.get(EvidenceRow, evidence_id)
        return Evidence.model_validate(row, from_attributes=True) if row else None

    def save_evaluation(self, criterion: AcceptanceCriterion, evidence: Evidence) -> None:
        self.session.add(
            EvidenceRow(
                **evidence.model_dump(exclude={"structured_data"}),
                structured_data=evidence.structured_data.model_dump(mode="json"),
            )
        )
        self.session.flush()
        self.save_criterion(criterion)

    def save_criterion(self, criterion: AcceptanceCriterion) -> None:
        self.session.execute(
            update(CriterionRow)
            .where(CriterionRow.id == criterion.id)
            .values(
                status=criterion.status,
                attempt_count=criterion.attempt_count,
                last_validated_at=criterion.last_validated_at,
                evidence_refs=[str(ref) for ref in criterion.evidence_refs],
            )
        )
