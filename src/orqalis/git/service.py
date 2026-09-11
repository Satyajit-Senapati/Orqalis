import os
import re
import subprocess
from pathlib import Path

from orqalis.domain.errors import OrqalisError, PolicyDeniedError
from orqalis.git.contracts import GitStatus


class GitError(OrqalisError):
    code = "git_error"


def validate_relative_path(path: str) -> None:
    if not path or path.startswith(("/", "\\")) or "\\" in path:
        raise PolicyDeniedError("Expected a repository-relative POSIX path")
    if (
        any(
            part.casefold() in {"", ".", "..", ".git"}
            or part.endswith((".", " "))
            or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part)
            for part in path.split("/")
        )
        or ":" in path
        or any(ord(char) < 32 for char in path)
    ):
        raise PolicyDeniedError("Unsafe repository path")


class LocalGitService:
    """Small explicit Git surface; no shell strings or arbitrary public commands."""

    def __init__(self, timeout_seconds: float = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def _execute(
        self,
        path: Path,
        args: tuple[str, ...],
        input_bytes: bytes | None = None,
        identity_env: dict[str, str] | None = None,
    ) -> bytes:
        # Strip inherited Git overrides so callers cannot redirect the repository/index.
        env = {
            key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")
        }
        env.update(
            {"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0", "GCM_INTERACTIVE": "never"}
        )
        if identity_env:
            allowed = {
                "GIT_AUTHOR_NAME",
                "GIT_AUTHOR_EMAIL",
                "GIT_AUTHOR_DATE",
                "GIT_COMMITTER_NAME",
                "GIT_COMMITTER_EMAIL",
                "GIT_COMMITTER_DATE",
            }
            if not set(identity_env) <= allowed:
                raise PolicyDeniedError("Unexpected Git identity environment key")
            env.update(identity_env)
        try:
            result = subprocess.run(
                [
                    "git",
                    "-c",
                    "core.fsmonitor=false",
                    "-c",
                    f"core.hooksPath={os.devnull}",
                    "-C",
                    str(path),
                    *args,
                ],
                env=env,
                capture_output=True,
                input=input_bytes,
                check=False,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GitError("Git is unavailable or timed out") from exc
        if result.returncode:
            # stderr can include remote credentials, user config, or unsafe filenames.
            raise GitError(f"Git {args[0]} failed with exit code {result.returncode}")
        return result.stdout

    def root(self, path: Path) -> Path:
        resolved = path.expanduser().resolve(strict=True)
        if resolved.is_file():
            resolved = resolved.parent
        root = self._execute(resolved, ("rev-parse", "--show-toplevel")).decode().strip()
        return Path(root).resolve(strict=True)

    def resolve_commit(self, path: Path, revision: str) -> str:
        if not revision or revision.startswith("-") or "\x00" in revision:
            raise PolicyDeniedError("Invalid Git revision")
        return (
            self._execute(
                path, ("rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}")
            )
            .decode()
            .strip()
        )

    def has_commit(self, path: Path, revision: str) -> bool:
        try:
            self.resolve_commit(path, revision)
        except GitError:
            return False
        return True

    def status(self, path: Path) -> GitStatus:
        root = self.root(path)
        head = self.resolve_commit(root, "HEAD")
        branch = self._execute(root, ("rev-parse", "--abbrev-ref", "HEAD")).decode().strip()
        raw = self._execute(root, ("status", "--porcelain=v1", "-z", "--untracked-files=all"))
        records = iter(raw.decode("utf-8", errors="surrogateescape").split("\x00"))
        paths: set[str] = set()
        for record in records:
            if not record:
                continue
            paths.add(record[3:])
            if "R" in record[:2] or "C" in record[:2]:
                paths.add(next(records))
        return GitStatus(
            repo_root=root,
            branch=None if branch == "HEAD" else branch,
            head=head,
            changed_paths=tuple(sorted(paths)),
        )

    def changed_files(self, path: Path, base: str, head: str) -> tuple[str, ...]:
        base_sha = self.resolve_commit(path, base)
        head_sha = self.resolve_commit(path, head)
        raw = self._execute(
            path, ("diff", "--name-only", "--no-renames", "-z", base_sha, head_sha, "--")
        )
        return tuple(item for item in raw.decode("utf-8").split("\x00") if item)

    def tracked_files(self, path: Path, commit: str = "HEAD") -> tuple[str, ...]:
        return tuple(
            item
            for item in self._execute(
                path, ("ls-tree", "-r", "--name-only", "-z", self.resolve_commit(path, commit))
            )
            .decode("utf-8")
            .split("\x00")
            if item
        )

    def read_file(self, path: Path, commit: str, relative_path: str) -> bytes:
        validate_relative_path(relative_path)
        sha = self.resolve_commit(path, commit)
        return self._execute(path, ("show", f"{sha}:{relative_path}"))

    def common_directory(self, path: Path) -> Path:
        return Path(
            self._execute(path, ("rev-parse", "--path-format=absolute", "--git-common-dir"))
            .decode()
            .strip()
        ).resolve()

    def log_range(self, path: Path, base: str, head: str) -> tuple[str, ...]:
        base_sha = self.resolve_commit(path, base)
        head_sha = self.resolve_commit(path, head)
        return tuple(
            self._execute(path, ("rev-list", f"{base_sha}..{head_sha}")).decode().splitlines()
        )

    def validate_branch(self, path: Path, branch: str, protected: tuple[str, ...]) -> None:
        if (
            branch in protected
            or branch.startswith("-")
            or not re.fullmatch(r"[A-Za-z0-9_./-]+", branch)
        ):
            raise PolicyDeniedError("Branch is protected or invalid")
        self._execute(path, ("check-ref-format", "--branch", branch))

    def create_worktree(
        self, repo: Path, target: Path, branch: str, base: str, protected: tuple[str, ...]
    ) -> None:
        self.validate_branch(repo, branch, protected)
        sha = self.resolve_commit(repo, base)
        # -b fails if branch exists; never switch or repurpose an existing branch.
        self._execute(repo, ("worktree", "add", "-b", branch, str(target), sha))

    def remove_worktree(self, repo: Path, target: Path) -> None:
        if self.status(target).changed_paths:
            raise PolicyDeniedError("Workspace contains changes; cleanup denied")
        self._execute(repo, ("worktree", "remove", str(target)))

    def read_file_if_present(
        self, path: Path, commit: str, relative_path: str, max_bytes: int
    ) -> bytes | None:
        validate_relative_path(relative_path)
        sha = self.resolve_commit(path, commit)
        metadata = self._execute(path, ("ls-tree", "-l", sha, "--", relative_path))
        if not metadata:
            return None
        fields = metadata.split(b"\t", 1)[0].split()
        if fields[0] not in {b"100644", b"100755"} or fields[1] != b"blob":
            return None
        if int(fields[3]) > max_bytes:
            return None
        return self.read_file(path, sha, relative_path)

    def diff_text(self, path: Path, base: str, relative_path: str) -> bytes:
        validate_relative_path(relative_path)
        sha = self.resolve_commit(path, base)
        return self._execute(
            path,
            (
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                "--unified=0",
                sha,
                "--",
                relative_path,
            ),
        )
