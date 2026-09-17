"""Application service for building and persisting a Task Capsule context stage."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from orqalis.context.builder import ProjectContextBuilder
from orqalis.context.models import ProjectContextPack
from orqalis.domain.errors import ConflictError, NotFoundError, PolicyDeniedError
from orqalis.persistence.filesystem.layout import resolve_project_root
from orqalis.persistence.filesystem.task_store import TaskCapsuleStore
from orqalis.security.redaction import safe_diagnostic


class TaskContextService:
    """Build selective context and commit it with the owning Task Capsule."""

    def __init__(
        self,
        root: Path,
        *,
        builder: ProjectContextBuilder | None = None,
        store: TaskCapsuleStore | None = None,
    ) -> None:
        self.root = resolve_project_root(root)
        self.builder = builder
        self.store = store or TaskCapsuleStore.from_root(self.root)
        if self.store.root != self.root or (
            self.builder is not None and self.builder.root != self.root
        ):
            raise ValueError("Context builder and Task Capsule store must share a project root")

    def create(
        self,
        run_id: UUID,
        task: str | None = None,
        max_chars: int | None = None,
    ) -> ProjectContextPack:
        with self.store.unit_of_work() as uow:
            run = uow.runs.get(run_id)
            if run is None:
                raise NotFoundError("Task Capsule not found")
            query = task if task is not None else run.request
        builder = self.builder or ProjectContextBuilder(self.root)
        pack = builder.build(query, max_chars)
        if safe_diagnostic(pack.model_dump_json()) != pack.model_dump_json():
            raise PolicyDeniedError("Task context contains credentials or secrets")
        with self.store.unit_of_work() as uow:
            run = uow.runs.get(run_id, for_update=True)
            if run is None:
                raise NotFoundError("Task Capsule not found")
            if pack.project_id != str(run.project_id):
                raise ConflictError("Context Pack belongs to another project")
            uow.session.save_extension(run_id, "context", pack.model_dump(mode="json"))
            uow.commit()
        return pack

    def get(self, run_id: UUID) -> ProjectContextPack | None:
        with self.store.unit_of_work() as uow:
            if uow.runs.get(run_id) is None:
                raise NotFoundError("Task Capsule not found")
            value = uow.session.extension(run_id, "context")
        if value is None:
            return None
        try:
            return ProjectContextPack.model_validate(value)
        except ValidationError as exc:
            raise ConflictError("Task Capsule context stage is invalid") from exc


__all__ = ["TaskContextService"]
