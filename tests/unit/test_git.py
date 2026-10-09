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


@pytest.mark.parametrize(
    "state", ["mixed", "renamed", "detached", "conflicted", "upstream", "submodule", "copied"]
)
def test_status_matches_original_porcelain_contract(git_repo: Path, state: str) -> None:
    from orqalis.git.contracts import GitStatus

    if state == "mixed":
        (git_repo / "main.py").write_text("changed locally\n", encoding="utf-8")
        (git_repo / "tests/test_main.py").unlink()
        (git_repo / "new name.txt").write_text("new\n", encoding="utf-8")
        (git_repo / "unicode-caf\u00e9.txt").write_text("unicode\n", encoding="utf-8")
        (git_repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        (git_repo / "ignored.txt").write_text("ignored\n", encoding="utf-8")
        git(git_repo, "add", "unicode-caf\u00e9.txt")
    elif state == "renamed":
        git(git_repo, "mv", "main.py", "renamed with spaces.py")
    elif state == "detached":
        git(git_repo, "checkout", "--detach", "HEAD")
    elif state == "upstream":
        git(git_repo, "branch", "status-upstream")
        git(git_repo, "branch", "--set-upstream-to=status-upstream", "main")
    elif state == "submodule":
        # The cloned local fixture is owned; no network or global Git config is used.
        git(
            git_repo,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            str(git_repo),
            "modules/sub",
        )
        git(
            git_repo,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-am",
            "submodule",
        )
        (git_repo / "modules/sub/main.py").write_text("dirty submodule\n", encoding="utf-8")
        (git_repo / "modules/sub/new.txt").write_text("untracked\n", encoding="utf-8")
    elif state == "copied":
        git(git_repo, "config", "status.renames", "copies")
        source = git_repo / "main.py"
        (git_repo / "copy.py").write_bytes(source.read_bytes())
        source.write_text("changed source\n", encoding="utf-8")
        git(git_repo, "add", "main.py", "copy.py")
    else:
        git(git_repo, "switch", "-c", "status-other")
        (git_repo / "main.py").write_text("other\n", encoding="utf-8")
        git(
            git_repo,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-am",
            "other",
        )
        git(git_repo, "switch", "main")
        (git_repo / "main.py").write_text("main\n", encoding="utf-8")
        git(
            git_repo,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-am",
            "main",
        )
        with pytest.raises(subprocess.CalledProcessError):
            git(git_repo, "merge", "status-other")

    class RecordingGit(LocalGitService):
        def __init__(self) -> None:
            super().__init__()
            self.commands: list[tuple[str, ...]] = []

        def _execute(
            self,
            path: Path,
            args: tuple[str, ...],
            input_bytes: bytes | None = None,
            identity_env: dict[str, str] | None = None,
        ) -> bytes:
            self.commands.append(args)
            return super()._execute(path, args, input_bytes, identity_env)

    original = LocalGitService()
    root = original.root(git_repo)
    head = original.resolve_commit(root, "HEAD")
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    records = iter(
        original._execute(root, ("status", "--porcelain=v1", "-z", "--untracked-files=all"))
        .decode("utf-8", errors="surrogateescape")
        .split("\x00")
    )
    expected_paths: set[str] = set()
    for record in records:
        if record:
            expected_paths.add(record[3:])
            if "R" in record[:2] or "C" in record[:2]:
                expected_paths.add(next(records))
    expected = GitStatus(
        repo_root=root,
        head=head,
        branch=None if branch == "HEAD" else branch,
        changed_paths=tuple(sorted(expected_paths)),
    )
    service = RecordingGit()
    # Nested-directory root resolution must still precede the complete status read.
    assert service.status(git_repo / "tests") == expected
    assert len(service.commands) == 2
    assert service.commands[0] == ("rev-parse", "--show-toplevel")
    assert "--no-ahead-behind" in service.commands[1]
    if state == "submodule":
        assert expected.changed_paths == ("modules/sub",)
    if state == "mixed":
        assert "ignored.txt" not in expected.changed_paths


def test_status_requires_committed_head(tmp_path: Path) -> None:
    root = tmp_path / "unborn"
    root.mkdir()
    git(root, "init", "-b", "main")
    with pytest.raises(GitError):
        LocalGitService().status(root)


def test_status_preserves_nul_delimited_raw_filenames(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    head = "a" * 40
    raw = (
        f"# branch.oid {head}\0# branch.head main\0# future.header ignored\0"
        f"1 .M N... 100644 100644 100644 {head} {head} tracked space\tname\n.py\0"
        f"2 C. N... 100644 100644 100644 {head} {head} C100 copy target.py\0"
        "original source.py\0? \u00e9 untracked.txt\0? "
    ).encode() + b"raw-\xff.txt\0"
    service = LocalGitService()
    monkeypatch.setattr(service, "root", lambda path: git_repo)
    monkeypatch.setattr(service, "_execute", lambda *args: raw)
    status = service.status(git_repo)
    assert status.head == head and status.branch == "main"
    assert set(status.changed_paths) == {
        "tracked space\tname\n.py",
        "copy target.py",
        "original source.py",
        "\u00e9 untracked.txt",
        "raw-\udcff.txt",
    }


@pytest.mark.parametrize("body", [b"1 malformed\0", b"2 malformed\0", b"? \0", b"x unknown\0"])
def test_status_fails_closed_on_invalid_document(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    service = LocalGitService()
    monkeypatch.setattr(service, "root", lambda path: git_repo)
    raw = b"# branch.oid " + b"a" * 40 + b"\0# branch.head main\0" + body
    monkeypatch.setattr(service, "_execute", lambda *args: raw)
    with pytest.raises(GitError):
        service.status(git_repo)


@pytest.mark.parametrize("suffix", [b"", b"\0? file\0", b"# branch.head other\0"])
def test_status_rejects_incomplete_or_ambiguous_metadata(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, suffix: bytes
) -> None:
    service = LocalGitService()
    monkeypatch.setattr(service, "root", lambda path: git_repo)
    raw = b"# branch.oid " + b"a" * 40 + b"\0# branch.head main"
    malformed = raw if suffix == b"" else raw + b"\0" + suffix
    monkeypatch.setattr(service, "_execute", lambda *args: malformed)
    with pytest.raises(GitError):
        service.status(git_repo)


def test_repository_location_pair_preserves_root_file_and_worktree_locations(
    git_repo: Path, tmp_path: Path
) -> None:
    service = LocalGitService()
    for path in (git_repo, git_repo / "tests/test_main.py"):
        assert service.root_and_common_directory(path) == (
            service.root(path),
            service.common_directory(git_repo),
        )
    worktree = tmp_path / "location worktree"
    git(git_repo, "worktree", "add", "-b", "location-pair", str(worktree))
    assert service.root_and_common_directory(worktree) == (
        worktree.resolve(),
        service.common_directory(git_repo),
    )
    with pytest.raises(FileNotFoundError):
        service.root_and_common_directory(tmp_path / "missing-location")


@pytest.mark.parametrize(
    "output", [b"", b"one\n", b"one\ntwo\nthree\n", b"relative\nalso-relative\n"]
)
def test_repository_location_pair_ambiguous_output_uses_original_methods(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, output: bytes
) -> None:
    service = LocalGitService()
    calls: list[tuple[str, Path]] = []
    original_input = git_repo / "tests/test_main.py"

    def root(path: Path) -> Path:
        calls.append(("root", path))
        return git_repo

    def common(path: Path) -> Path:
        calls.append(("common", path))
        return git_repo / ".git"

    monkeypatch.setattr(service, "_execute", lambda *args: output)
    monkeypatch.setattr(service, "root", root)
    monkeypatch.setattr(service, "common_directory", common)
    assert service.root_and_common_directory(original_input) == (git_repo, git_repo / ".git")
    assert calls == [("root", original_input), ("common", git_repo)]


def test_repository_location_pair_command_failure_never_retries(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = LocalGitService()

    def denied(*args: object) -> bytes:
        raise GitError("location read denied")

    def unexpected(path: Path) -> Path:
        pytest.fail("A failed Git operation must not fall back or retry")

    monkeypatch.setattr(service, "_execute", denied)
    monkeypatch.setattr(service, "root", unexpected)
    monkeypatch.setattr(service, "common_directory", unexpected)
    with pytest.raises(GitError, match="location read denied"):
        service.root_and_common_directory(git_repo)
