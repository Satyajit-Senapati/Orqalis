from collections.abc import Callable
from pathlib import Path

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.domain.errors import ConflictError, NotFoundError, PolicyDeniedError
from orqalis.domain.project import Project, ProjectSettings
from orqalis.git.contracts import GitService, GitStatus
from orqalis.git.inspection import inspect_paths


class ProjectService:
    """Shared project use cases with persistence and Git supplied through ports."""

    def __init__(self, unit_of_work: Callable[[], ProjectUnitOfWork], git: GitService) -> None:
        self.unit_of_work = unit_of_work
        self.git = git

    def initialize(self, path: Path, settings: ProjectSettings | None = None) -> Project:
        status = self.git.status(path)
        if not status.branch:
            raise PolicyDeniedError("Initialize on a named branch, not detached HEAD")
        with self.unit_of_work() as uow:
            existing = uow.projects.get_by_root(status.repo_root)
            if existing:
                return existing
            profile = inspect_paths(self.git.tracked_files(status.repo_root))
            project = Project(
                name=status.repo_root.name,
                repo_root=status.repo_root,
                default_branch=status.branch,
                settings=(settings or ProjectSettings()).model_copy(
                    update={"repository_profile": profile}
                ),
            )
            try:
                uow.projects.add(project)
                uow.commit()
            except ConflictError:
                uow.rollback()
                existing = uow.projects.get_by_root(status.repo_root)
                if not existing:
                    raise
                return existing
            return project

    def status(self, path: Path) -> tuple[Project, GitStatus]:
        git_status = self.git.status(path)
        with self.unit_of_work() as uow:
            project = uow.projects.get_by_root(git_status.repo_root)
            if not project:
                raise NotFoundError("Project is not initialized; run orqalis init")
            return project, git_status
