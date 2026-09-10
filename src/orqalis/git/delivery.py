import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from orqalis.domain.delivery import ChangeReport, DeliveryPolicy
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.domain.execution import RunWorkspace
from orqalis.execution.filesystem import ScopedFilesystem
from orqalis.execution.review import workspace_digest
from orqalis.git.service import LocalGitService
from orqalis.security.redaction import safe_diagnostic


class GitDeliveryService:
    """Explicit blob staging and compare-and-swap branch updates; no force/history reset."""

    def __init__(self, git: LocalGitService) -> None:
        self.git = git

    def stage(
        self, workspace: RunWorkspace, report: ChangeReport, protected: tuple[str, ...]
    ) -> str:
        self.git.validate_branch(workspace.path, workspace.branch, protected)
        if not report.passed or report.tree_hash != workspace_digest(workspace, self.git):
            raise PolicyDeniedError("Change Guardian approval does not match the current tree")
        staged = (
            self.git._execute(
                workspace.path,
                (
                    "diff",
                    "--cached",
                    "--name-only",
                    "-z",
                    workspace.base_commit,
                    "--",
                ),
            )
            .decode()
            .split("\x00")
        )
        paths = {change.path for change in report.changes}
        if any(path and path not in paths for path in staged):
            raise PolicyDeniedError("Index contains unrelated changes")
        files = ScopedFilesystem(workspace.path, workspace.policy)
        for change in report.changes:
            if change.status == "deleted":
                self.git._execute(
                    workspace.path, ("update-index", "--force-remove", "--", change.path)
                )
                continue
            target = files.target(change.path)
            # No user-defined clean/smudge/process filter is executed during staging.
            blob = (
                self.git._execute(
                    workspace.path,
                    (
                        "hash-object",
                        "-w",
                        "--no-filters",
                        "--",
                        change.path,
                    ),
                )
                .decode()
                .strip()
            )
            previous = self.git._execute(
                workspace.path,
                (
                    "ls-tree",
                    workspace.base_commit,
                    "--",
                    change.path,
                ),
            )
            mode = (
                previous.split()[0].decode()
                if previous
                else ("100755" if os.name != "nt" and target.stat().st_mode & 0o111 else "100644")
            )
            if mode not in {"100644", "100755"}:
                raise PolicyDeniedError("Only regular files may be delivered")
            self.git._execute(
                workspace.path, ("update-index", "--add", "--cacheinfo", mode, blob, change.path)
            )
        if workspace_digest(workspace, self.git) != report.tree_hash:
            raise ConflictError("Workspace changed while staging")
        return self.git._execute(workspace.path, ("write-tree",)).decode().strip()

    def create_commit(
        self,
        workspace: RunWorkspace,
        tree_sha: str,
        message: str,
        at: datetime,
        policy: DeliveryPolicy,
    ) -> str:
        if safe_diagnostic(message) != message or not message.strip():
            raise PolicyDeniedError("Commit message contains unsafe content")
        timestamp = at.isoformat()
        env = {"GIT_AUTHOR_DATE": timestamp, "GIT_COMMITTER_DATE": timestamp}
        if policy.author_name and policy.author_email:
            env.update(
                GIT_AUTHOR_NAME=policy.author_name,
                GIT_COMMITTER_NAME=policy.author_name,
                GIT_AUTHOR_EMAIL=policy.author_email,
                GIT_COMMITTER_EMAIL=policy.author_email,
            )
        return (
            self.git._execute(
                workspace.path,
                ("commit-tree", tree_sha, "-p", workspace.base_commit),
                input_bytes=message.encode("utf-8"),
                identity_env=env,
            )
            .decode()
            .strip()
        )

    def attach(self, workspace: RunWorkspace, commit: str, protected: tuple[str, ...]) -> None:
        self.git.validate_branch(workspace.path, workspace.branch, protected)
        current = self.git.status(workspace.path)
        if current.branch != workspace.branch:
            raise PolicyDeniedError("Workspace branch changed")
        if current.head == commit:
            return
        if current.head != workspace.base_commit:
            raise ConflictError("Branch advanced outside this run")
        self.git._execute(
            workspace.path,
            (
                "update-ref",
                f"refs/heads/{workspace.branch}",
                commit,
                workspace.base_commit,
            ),
        )

    def push(
        self,
        workspace: RunWorkspace,
        commit: str,
        policy: DeliveryPolicy,
        protected: tuple[str, ...],
    ) -> None:
        if not policy.push:
            raise PolicyDeniedError("Push is not authorized by delivery policy")
        self.git.validate_branch(workspace.path, workspace.branch, protected)
        state = self.git.status(workspace.path)
        if state.branch != workspace.branch or state.head != commit or state.changed_paths:
            raise PolicyDeniedError("Only the accepted run commit may be pushed")
        remote = (
            self.git._execute(
                workspace.path, ("remote", "get-url", "--push", "--all", policy.remote)
            )
            .decode()
            .strip()
        )
        if len(remote.splitlines()) != 1:
            raise PolicyDeniedError("Exactly one push destination is required")
        if safe_diagnostic(remote) != remote:
            raise PolicyDeniedError("Remote URL embeds credentials")
        parsed = urlsplit(remote)
        local = Path(remote).is_absolute() or parsed.scheme == "file"
        ssh_style = "@" in remote and ":" in remote and "::" not in remote and not parsed.scheme
        if not (
            parsed.scheme in {"https", "ssh"} or ssh_style or (local and policy.allow_local_remote)
        ):
            raise PolicyDeniedError("Remote transport is not permitted")
        self.git._execute(
            workspace.path,
            (
                "-c",
                "protocol.ext.allow=never",
                "-c",
                "core.sshCommand=ssh -oBatchMode=yes",
                "push",
                "--porcelain",
                "--receive-pack=git-receive-pack",
                remote,
                f"{commit}:refs/heads/{workspace.branch}",
            ),
        )
