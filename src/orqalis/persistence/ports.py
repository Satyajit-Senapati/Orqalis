from pathlib import Path
from typing import Protocol
from uuid import UUID

from orqalis.domain.project import Project


class ProjectRepository(Protocol):
    def get(self, project_id: UUID) -> Project | None: ...

    def get_by_root(self, root: Path) -> Project | None: ...

    def list(self) -> tuple[Project, ...]: ...
    def add(self, project: Project) -> Project: ...
