from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from orqalis.domain.errors import ConflictError
from orqalis.domain.project import Project, ProjectSettings
from orqalis.persistence.models import ProjectRow


def to_project(row: ProjectRow) -> Project:
    return Project(
        id=row.id,
        name=row.name,
        repo_uri=row.repo_uri,
        repo_root=Path(row.repo_root),
        default_branch=row.default_branch,
        settings=ProjectSettings.model_validate(row.settings),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SQLProjectRepository:
    """Transaction ownership stays with the application service."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, project_id: UUID) -> Project | None:
        row = self.session.get(ProjectRow, project_id)
        return to_project(row) if row else None

    def get_by_root(self, root: Path) -> Project | None:
        row = self.session.scalar(select(ProjectRow).where(ProjectRow.repo_root == str(root)))
        return to_project(row) if row else None

    def list(self) -> tuple[Project, ...]:
        return tuple(
            to_project(row)
            for row in self.session.scalars(
                select(ProjectRow).order_by(ProjectRow.name, ProjectRow.id)
            )
        )

    def add(self, project: Project) -> Project:
        self.session.add(
            ProjectRow(
                id=project.id,
                name=project.name,
                repo_uri=project.repo_uri,
                repo_root=str(project.repo_root),
                default_branch=project.default_branch,
                settings=project.settings.model_dump(mode="json"),
                created_at=project.created_at,
                updated_at=project.updated_at,
            )
        )
        try:
            self.session.flush()
        except IntegrityError as exc:
            raise ConflictError("Project identity already exists") from exc
        return project
