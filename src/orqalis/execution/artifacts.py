import hashlib
from uuid import uuid5

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.domain.artifact import Artifact
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.domain.execution import RunWorkspace, WorkerResult
from orqalis.domain.task import TaskExecution
from orqalis.execution.filesystem import ScopedFilesystem


def record_artifacts(
    uow: ProjectUnitOfWork,
    workspace: RunWorkspace,
    attempt: TaskExecution,
    result: WorkerResult,
) -> None:
    """Record bounded, scoped file outputs atomically with the caller's receipt."""
    files = ScopedFilesystem(workspace.path, workspace.policy)
    existing = {item.id: item for item in uow.delivery.artifacts(workspace.run_id)}
    for path in dict.fromkeys(result.artifact_paths):
        target = files.target(path, write=True)
        if not target.is_file() or target.stat().st_size > workspace.policy.max_file_bytes:
            raise PolicyDeniedError("Reported artifact is missing or oversized")
        content = target.read_bytes()
        if len(content) > workspace.policy.max_file_bytes:
            raise PolicyDeniedError("Reported artifact exceeds the file limit")
        artifact = Artifact(
            id=uuid5(attempt.id, path),
            run_id=workspace.run_id,
            task_id=attempt.task_id,
            type="implementation",
            path_or_uri=str(target),
            content_hash=hashlib.sha256(content).hexdigest(),
        )
        previous = existing.get(artifact.id)
        if previous:
            if (previous.path_or_uri, previous.content_hash) != (
                artifact.path_or_uri,
                artifact.content_hash,
            ):
                raise ConflictError("Reported artifact changed after its persisted receipt")
        else:
            uow.delivery.save_artifact(artifact)
