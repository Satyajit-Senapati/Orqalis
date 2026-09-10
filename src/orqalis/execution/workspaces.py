from collections.abc import Callable
from uuid import UUID

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import locked_run
from orqalis.domain.errors import ConflictError, NotFoundError, PolicyDeniedError
from orqalis.domain.execution import ExecutionPolicy, RunWorkspace
from orqalis.git.service import LocalGitService
from orqalis.workspace.manager import WorktreeManager


class ExecutionWorkspaces:
    def __init__(self, factory: Callable[[], ProjectUnitOfWork], manager: WorktreeManager) -> None:
        self.factory, self.manager = factory, manager

    def ensure(self, run_id: UUID, policy: ExecutionPolicy) -> RunWorkspace:
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            project = uow.projects.get(run.project_id)
            if project is None:
                raise NotFoundError("Project not found")
            existing = uow.execution.workspace(run_id)
            if existing and existing.policy != policy:
                raise ConflictError("Workspace execution policy cannot change during a run")
            owned = self.manager.get(run_id)
            if owned is None:
                owned = self.manager.create(project, run.id, run.target_branch, run.base_commit)
            if (
                owned.project_id != project.id
                or owned.repo_root != project.repo_root
                or owned.branch != run.target_branch
                or owned.base_commit != run.base_commit
            ):
                raise PolicyDeniedError("Workspace identity differs from the persisted run")
            binding = RunWorkspace(
                run_id=run_id,
                path=owned.path,
                branch=owned.branch,
                base_commit=owned.base_commit,
                policy=policy,
            )
            if existing and existing != binding:
                raise ConflictError("Workspace binding changed")
            if existing is None:
                uow.execution.save_workspace(binding)
                uow.commit()
            return binding


def verify_workspace(workspace: RunWorkspace, git: LocalGitService) -> None:
    state = git.status(workspace.path)
    if state.repo_root != workspace.path.resolve() or state.branch != workspace.branch:
        raise PolicyDeniedError("Workspace identity or branch changed")
    if state.head != workspace.base_commit:
        raise PolicyDeniedError("Workspace HEAD changed outside the delivery service")
