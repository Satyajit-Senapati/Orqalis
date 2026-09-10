import hashlib
from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid5

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit, locked_run
from orqalis.domain.agent import ActorStatus, AgentRole
from orqalis.domain.artifact import Artifact
from orqalis.domain.base import utc_now
from orqalis.domain.delivery import ChangeReport, DeliveryPolicy
from orqalis.domain.errors import ConflictError, NotFoundError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.execution.filesystem import ScopedFilesystem
from orqalis.security.redaction import safe_diagnostic


class DocumentationService:
    """Documents accepted facts and actual diff; never invents implementation behavior."""

    def __init__(self, factory: Callable[[], ProjectUnitOfWork]) -> None:
        self.factory = factory

    def write(
        self, run_id: UUID, actor_id: UUID, report: ChangeReport, policy: DeliveryPolicy
    ) -> Artifact:
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            actor = next((item for item in uow.runtime.actors(run_id) if item.id == actor_id), None)
            workspace = uow.execution.workspace(run_id)
            goal = (
                uow.runs.get_goal(run.current_goal_version_id)
                if run.current_goal_version_id
                else None
            )
            reviews = uow.execution.reviews(run_id)
            if workspace is None or goal is None or not reviews or not report.passed:
                raise NotFoundError("Accepted implementation context is missing")
            if (
                actor is None
                or actor.role != AgentRole.DOCUMENTATION
                or actor.status != ActorStatus.WORKING
            ):
                raise PolicyDeniedError(
                    "Documentation requires an assigned active documentation actor"
                )
            review = reviews[-1]
            if review.result.overall != "PASS":
                raise PolicyDeniedError("Documentation requires accepted implementation")
            artifact_id = uuid5(run_id, f"documentation:{review.id}")
            existing = next(
                (item for item in uow.delivery.artifacts(run_id) if item.id == artifact_id), None
            )
            if existing:
                if (
                    hashlib.sha256(Path(existing.path_or_uri).read_bytes()).hexdigest()
                    != existing.content_hash
                ):
                    raise ConflictError("Documentation artifact changed after its checkpoint")
                return existing
            lines = [
                f"## Orqalis run {run_id}",
                "",
                goal.goal.goal,
                "",
                f"Base commit: {run.base_commit}",
                f"Goal version: {goal.goal.version}",
                f"Accepted review: {review.id}",
                "",
                "Changes:",
                "",
                *(
                    f"- {change.status}: {change.path} "
                    f"(+{change.added_lines}/-{change.deleted_lines})"
                    for change in report.changes
                ),
                "",
                "Validation:",
                "",
                *(
                    f"- {criterion.key}: {criterion.status} ({criterion.validation_spec.kind}); "
                    f"evidence: {', '.join(str(ref) for ref in criterion.evidence_refs)}"
                    for criterion in goal.criteria
                ),
            ]
            content = "\n".join(lines) + "\n"
            if safe_diagnostic(content) != content:
                raise PolicyDeniedError("Unsafe documentation content")
            if policy.documentation_path:
                path = policy.documentation_path
                if Path(path).suffix.lower() not in {".md", ".rst", ".txt"}:
                    raise PolicyDeniedError("Documentation path must be a text documentation file")
                files = ScopedFilesystem(workspace.path, workspace.policy)
                target = files.target(path, write=True)
                original = target.read_text(encoding="utf-8") if target.is_file() else ""
                if safe_diagnostic(original) != original:
                    raise PolicyDeniedError("Existing documentation contains sensitive data")
                begin, end = f"<!-- orqalis:{run_id}:begin -->", f"<!-- orqalis:{run_id}:end -->"
                block = f"{begin}\n{content}{end}"
                if begin in original:
                    start = original.index(begin)
                    finish = original.find(end, start)
                    if finish < 0:
                        raise ConflictError("Existing run documentation marker is incomplete")
                    content = original[:start] + block + original[finish + len(end) :]
                else:
                    content = original.rstrip() + "\n\n" + block + "\n"
                digest = files.write(path, content)
            else:
                target = workspace.path.parent / ".artifacts" / str(run_id) / f"{review.id}.md"
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.is_symlink() or target.parent.is_symlink():
                    raise PolicyDeniedError("Unsafe artifact path")
                target.write_text(content, encoding="utf-8", newline="\n")
                digest = hashlib.sha256(content.encode()).hexdigest()
            artifact = Artifact(
                id=artifact_id,
                run_id=run_id,
                task_id=actor.current_task_id,
                type="documentation",
                path_or_uri=str(target),
                content_hash=digest,
            )
            uow.delivery.save_artifact(artifact)
            emit(
                uow,
                run,
                EventType.DOCUMENTATION_UPDATED,
                f"documentation:{artifact.id}",
                utc_now(),
                EventPayload(summary="Documented accepted changes and validation references"),
                actor_id,
            )
            uow.commit()
            return artifact
