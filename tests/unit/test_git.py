import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.domain.project import Project
from orqalis.git.inspection import inspect_paths
from orqalis.git.service import GitError, LocalGitService, validate_relative_path
from orqalis.workspace.manager import WorktreeManager


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def test_repository_detection_dirty_paths_and_committed_read(git_repo: Path) -> None:
    service = LocalGitService()
    assert service.root(git_repo / "tests/test_main.py") == git_repo
    status = service.status(git_repo)
    assert status.branch == "main"
    assert status.changed_paths == ()
    assert service.has_commit(git_repo, status.head)
    assert not service.has_commit(git_repo, "0" * 40)
    (git_repo / "main.py").write_text("changed locally\n")
    (git_repo / "with spaces.txt").write_text("untracked\n")
    assert service.status(git_repo).changed_paths == ("main.py", "with spaces.txt")
    assert service.read_file(git_repo, status.head, "main.py") == b"answer = 42\n"
    assert service.changed_files(git_repo, status.head, status.head) == ()
    profile = inspect_paths(service.tracked_files(git_repo))
    assert profile.languages == ("Python",)
    assert profile.build_manifests == ("pyproject.toml",)
    assert profile.instruction_paths == ("AGENTS.md",)
    assert profile.test_paths == ("tests/test_main.py",)


def test_rename_includes_old_and_new_paths(git_repo: Path) -> None:
    git(git_repo, "mv", "main.py", "renamed.py")
    assert LocalGitService().status(git_repo).changed_paths == ("main.py", "renamed.py")


@pytest.mark.parametrize("path", ["../secret", "/absolute", ".git/config", "C:/secret", "a/../b"])
def test_unsafe_relative_paths_denied(path: str) -> None:
    with pytest.raises(PolicyDeniedError):
        validate_relative_path(path)


def test_git_environment_cannot_redirect_repo(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_DIR", str(git_repo / "nonexistent"))
    assert LocalGitService().status(git_repo).branch == "main"


def test_worktree_create_cleanup_preserves_source(git_repo: Path, tmp_path: Path) -> None:
    service = LocalGitService()
    source_before = service.status(git_repo)
    manager = WorktreeManager(tmp_path / "workspaces", service)
    project = Project(name="fixture", repo_root=git_repo, default_branch="main")
    workspace = manager.create(project, uuid4(), "feature/test", "HEAD")
    assert service.status(workspace.path).branch == "feature/test"
    assert service.status(git_repo) == source_before
    with pytest.raises(ConflictError):
        manager.create(project, workspace.run_id, "feature/other", "HEAD")
    manager.remove(workspace)
    assert not workspace.path.exists()
    assert service.status(git_repo) == source_before
    # Cleanup deliberately retains branches; no implicit branch deletion.
    assert git(git_repo, "rev-parse", "feature/test") == source_before.head


def test_dirty_or_changed_branch_cleanup_denied(git_repo: Path, tmp_path: Path) -> None:
    service = LocalGitService()
    manager = WorktreeManager(tmp_path / "workspaces", service)
    project = Project(name="fixture", repo_root=git_repo, default_branch="main")
    workspace = manager.create(project, uuid4(), "feature/test", "HEAD")
    (workspace.path / "user-work.txt").write_text("retain me")
    with pytest.raises(PolicyDeniedError, match="changes"):
        manager.remove(workspace)
    git(workspace.path, "switch", "-c", "feature/user")
    with pytest.raises(PolicyDeniedError, match="identity"):
        manager.remove(workspace)
    assert (workspace.path / "user-work.txt").read_text() == "retain me"


@pytest.mark.parametrize("branch", ["main", "master", "--force", "../unsafe"])
def test_worktree_unsafe_branches_denied(git_repo: Path, tmp_path: Path, branch: str) -> None:
    manager = WorktreeManager(tmp_path / "workspaces", LocalGitService())
    project = Project(name="fixture", repo_root=git_repo, default_branch="main")
    with pytest.raises((PolicyDeniedError, GitError)):
        manager.create(project, uuid4(), branch, "HEAD")
    assert LocalGitService().status(git_repo).branch == "main"


def test_existing_branch_and_nested_workspace_denied(git_repo: Path, tmp_path: Path) -> None:
    git(git_repo, "branch", "feature/existing")
    project = Project(name="fixture", repo_root=git_repo, default_branch="main")
    with pytest.raises(GitError):
        WorktreeManager(tmp_path / "workspaces", LocalGitService()).create(
            project, uuid4(), "feature/existing", "HEAD"
        )
    with pytest.raises(PolicyDeniedError):
        WorktreeManager(git_repo / "nested", LocalGitService()).create(
            project, uuid4(), "feature/new", "HEAD"
        )
