import hashlib
from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid5

from orqalis.core.goals import GoalService
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit, locked_run
from orqalis.domain.acceptance import AcceptanceStatus
from orqalis.domain.agent import ActorStatus, AgentRole
from orqalis.domain.base import utc_now
from orqalis.domain.delivery import FinalValidation
from orqalis.domain.errors import NotFoundError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.task import TaskExecution
from orqalis.execution.cancellation import at_checkpoint
from orqalis.execution.evaluator import WorkspaceEvaluator
from orqalis.execution.filesystem import ScopedFilesystem
from orqalis.execution.review import workspace_digest
from orqalis.git.service import LocalGitService


class FinalValidationService:
    def __init__(
        self, factory: Callable[[], ProjectUnitOfWork], goals: GoalService, git: LocalGitService
    ) -> None:
        self.factory, self.goals, self.git = factory, goals, git

    async def validate(self, run_id: UUID, attempt: TaskExecution) -> FinalValidation:
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            workspace = uow.execution.workspace(run_id)
            if workspace is None:
                raise NotFoundError("Final validation workspace missing")
            actor = next(
                (
                    a
                    for a in uow.runtime.actors(run_id)
                    if a.id == attempt.assigned_actor_session_id
                ),
                None,
            )
            persisted = next(
                (a for a in uow.runtime.executions(run_id) if a.id == attempt.id), None
            )
            if (
                actor is None
                or actor.role != AgentRole.TESTER
                or actor.status != ActorStatus.WORKING
                or persisted != attempt
            ):
                raise PolicyDeniedError("Final validation requires an active assigned tester")
            before = workspace_digest(workspace, self.git)
            validation_id = uuid5(run_id, f"final:{attempt.id}:{before}")
            existing = next(
                (item for item in uow.delivery.validations(run_id) if item.id == validation_id),
                None,
            )
            if existing:
                return existing
        contract = self.goals.get(run_id)
        evidence_ids = []
        for criterion in contract.criteria:
            if criterion.validation_spec.kind in {"review", "manual"}:
                continue
            evidence = await at_checkpoint(
                self.goals.validate,
                run_id,
                criterion.key,
                WorkspaceEvaluator(workspace.path, workspace.policy),
                f"final:{validation_id}:{criterion.id}",
                attempt.id,
            )
            evidence_ids.append(evidence.id)
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            goal = (
                uow.runs.get_goal(run.current_goal_version_id)
                if run.current_goal_version_id
                else None
            )
            if goal is None or goal.goal.id != contract.goal.id:
                raise PolicyDeniedError("Goal changed during final validation")
            after = workspace_digest(workspace, self.git)
            passed = before == after and all(
                item.status == AcceptanceStatus.PASS
                for item in goal.criteria
                if item.priority == "required"
            )
            for artifact in uow.delivery.artifacts(run_id):
                if artifact.type == "documentation" and (
                    hashlib.sha256(Path(artifact.path_or_uri).read_bytes()).hexdigest()
                    != artifact.content_hash
                ):
                    passed = False
            reviews = uow.execution.reviews(run_id)
            if not reviews or reviews[-1].result.overall != "PASS":
                passed = False
            elif reviews:
                files = ScopedFilesystem(workspace.path, workspace.policy)
                for reviewed in reviews[-1].result.criteria:
                    for check in reviewed.source_checks:
                        if check.contains not in files.read(check.path):
                            passed = False
            result = FinalValidation(
                id=validation_id,
                run_id=run_id,
                actor_session_id=attempt.assigned_actor_session_id,
                goal_version_id=goal.goal.id,
                tree_hash=after,
                passed=passed,
                evidence_ids=tuple(evidence_ids),
            )
            uow.delivery.save_validation(result)
            emit(
                uow,
                run,
                EventType.FINAL_VALIDATION_COMPLETED,
                f"final:{validation_id}",
                utc_now(),
                EventPayload(status="PASS" if passed else "FAIL", evidence_ids=tuple(evidence_ids)),
                attempt.assigned_actor_session_id,
                attempt.task_id,
                attempt.id,
            )
            uow.commit()
            return result
