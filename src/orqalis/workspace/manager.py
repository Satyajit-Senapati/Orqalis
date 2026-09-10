import json
from pathlib import Path
from typing import Protocol
from uuid import UUID

from orqalis.domain.base import Contract
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.domain.project import Project
from orqalis.git.service import LocalGitService


class Workspace(Contract):
    run_id: UUID
    project_id: UUID
    repo_root: Path
    path: Path
    branch: str
    base_commit: str


class WorkspaceManager(Protocol):
    def create(self, project: Project, run_id: UUID, branch: str, base: str) -> Workspace: ...
    def remove(self, workspace: Workspace) -> None: ...


class WorktreeManager:
    """Owned worktrees outside the source tree, with fail-closed ownership manifests."""

    def __init__(self, root: Path, git: LocalGitService) -> None:
        self.root = root.resolve()
        self.git = git

    def _manifest(self, run_id: UUID) -> Path:
        return self.root / f"{run_id}.json"

    def create(self, project: Project, run_id: UUID, branch: str, base: str) -> Workspace:
        repo = self.git.root(project.repo_root)
        if self.root == repo or self.root.is_relative_to(repo):
            raise PolicyDeniedError("Workspace root must be outside the source repository")
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / str(run_id)
        if target.exists() or self._manifest(run_id).exists():
            raise ConflictError("Workspace already exists; refusing to overwrite")
        self.git.validate_branch(repo, branch, project.settings.protected_branches)
        workspace = Workspace(
            run_id=run_id,
            project_id=project.id,
            repo_root=repo,
            path=target,
            branch=branch,
            base_commit=self.git.resolve_commit(repo, base),
        )
        # Exclusive claim is retained on failure for safe inspection/recovery.
        try:
            with self._manifest(run_id).open("x", encoding="utf-8") as claim:
                claim.write(workspace.model_dump_json())
        except FileExistsError as exc:
            raise ConflictError("Workspace is already claimed") from exc
        self.git.create_worktree(
            repo, target, branch, workspace.base_commit, project.settings.protected_branches
        )
        return workspace

    def get(self, run_id: UUID) -> Workspace | None:
        manifest = self._manifest(run_id)
        if not manifest.exists():
            return None
        owned = Workspace.model_validate_json(manifest.read_text(encoding="utf-8"))
        if owned.run_id != run_id or owned.path.resolve() != self.root / str(run_id):
            raise PolicyDeniedError("Workspace ownership manifest is invalid")
        if not owned.path.is_dir():
            raise ConflictError("Workspace claim exists but creation is incomplete")
        state = self.git.status(owned.path)
        if state.repo_root != owned.path.resolve() or state.branch != owned.branch:
            raise PolicyDeniedError("Workspace identity has changed")
        if self.git.common_directory(owned.path) != self.git.common_directory(owned.repo_root):
            raise PolicyDeniedError("Workspace belongs to another repository")
        return owned

    def remove(self, workspace: Workspace) -> None:
        target = workspace.path.resolve()
        if target.parent != self.root or target.name != str(workspace.run_id):
            raise PolicyDeniedError("Workspace lies outside its owned directory")
        manifest = self._manifest(workspace.run_id)
        if not manifest.is_file():
            raise PolicyDeniedError("Workspace ownership manifest is missing")
        owned = Workspace.model_validate(json.loads(manifest.read_text(encoding="utf-8")))
        if owned != workspace:
            raise PolicyDeniedError("Workspace ownership does not match")
        status = self.git.status(target)
        if status.repo_root != target or status.branch != workspace.branch:
            raise PolicyDeniedError("Workspace branch or repository identity changed")
        common = self.git.common_directory(target)
        expected = self.git.common_directory(workspace.repo_root)
        if common != expected:
            raise PolicyDeniedError("Workspace is attached to a different repository")
        self.git.remove_worktree(workspace.repo_root, target)
        manifest.unlink()
