"""Host-owned Docker receipts; container lifetime is independent of the controller.

Application callers provide SandboxOwner outside the mounted worktree. Low-level
CommandRunner callers without an owner receive cleanup checks but no restart ledger.
"""

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field

from orqalis.domain.base import Contract
from orqalis.domain.errors import PolicyDeniedError
from orqalis.persistence.filesystem.io import (
    atomic_write_json,
    ensure_no_filesystem_links,
    read_json_object,
)
from orqalis.persistence.filesystem.layout import ProjectLayout
from orqalis.persistence.filesystem.locking import FileLock

_LABEL = "io.orqalis."
_ENV = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT"}


def _identity(path: Path) -> str:
    return hashlib.sha256(os.path.normcase(str(path.resolve())).encode()).hexdigest()


def docker_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key.upper() in _ENV}


def _docker(arguments: tuple[str, ...]) -> bytes:
    result = subprocess.run(
        ("docker", *arguments),
        env=docker_environment(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=15,
        check=False,
        creationflags=0x08000000 if os.name == "nt" else 0,
    )
    if result.returncode != 0:
        # Docker stderr can contain credentials from image/daemon configuration.
        raise PolicyDeniedError("Sandbox lifecycle operation could not be verified")
    return result.stdout


class SandboxReceipt(Contract):
    schema_version: Literal[1] = 1
    invocation_id: UUID
    daemon_identity: str | None = Field(default=None, min_length=1, max_length=256)
    run_id: UUID
    project_identity: str = Field(pattern=r"^[a-f0-9]{64}$")
    workspace_identity: str = Field(pattern=r"^[a-f0-9]{64}$")

    @property
    def name(self) -> str:
        return f"orqalis-{self.invocation_id.hex}"

    @property
    def labels(self) -> dict[str, str]:
        return {
            _LABEL + "project": self.project_identity,
            _LABEL + "workspace": self.workspace_identity,
            _LABEL + "run": str(self.run_id),
            _LABEL + "invocation": str(self.invocation_id),
        }


@dataclass(frozen=True)
class SandboxOwner:
    project_root: Path
    run_id: UUID

    def directory(self, workspace: Path) -> Path:
        project = self.project_root.resolve(strict=True)
        mount = workspace.resolve(strict=True)
        if project == mount or project.is_relative_to(mount):
            raise PolicyDeniedError("Sandbox receipts must be outside the writable workspace")
        layout = ProjectLayout(project)
        return layout.contained(layout.runtime / "sandboxes" / str(self.run_id))

    def receipt(self, workspace: Path) -> SandboxReceipt:
        return SandboxReceipt(
            invocation_id=uuid4(),
            run_id=self.run_id,
            project_identity=_identity(self.project_root),
            workspace_identity=_identity(workspace),
        )


def _daemon_identity() -> str:
    try:
        value = _docker(("info", "--format", "{{.ID}}")).decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise PolicyDeniedError("Docker daemon identity is invalid") from exc
    if not value or len(value) > 256 or any(char.isspace() for char in value):
        raise PolicyDeniedError("Docker daemon identity is unavailable")
    return value


def _remove_owned(receipt: SandboxReceipt) -> None:
    if receipt.daemon_identity != _daemon_identity():
        raise PolicyDeniedError("Docker daemon changed; original sandbox outcome is uncertain")

    # A successful list with no exact match distinguishes absence from daemon failure.
    def locate() -> str | None:
        raw = (
            _docker(
                (
                    "container",
                    "ls",
                    "--all",
                    "--no-trunc",
                    "--filter",
                    f"name=^/{receipt.name}$",
                    "--format",
                    "{{.ID}}",
                )
            )
            .decode("ascii", errors="replace")
            .strip()
        )
        if not raw:
            return None
        if not re.fullmatch(r"[a-f0-9]{64}", raw):
            raise PolicyDeniedError("Sandbox identity lookup is ambiguous")
        return raw

    container_id = locate()
    if container_id is None:
        return
    raw = _docker(("container", "inspect", "--format", "{{json .Config.Labels}}", container_id))
    try:
        labels = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PolicyDeniedError("Sandbox ownership response is invalid") from exc
    if not isinstance(labels, dict) or any(
        labels.get(key) != value for key, value in receipt.labels.items()
    ):
        raise PolicyDeniedError("Sandbox ownership differs from the persisted receipt")
    # Full ID prevents a name being replaced between inspection and removal.
    _docker(("container", "rm", "--force", "--volumes", container_id))
    if locate() is not None:
        raise PolicyDeniedError("Sandbox cleanup is incomplete")


def reconcile_sandboxes(owner: SandboxOwner, workspace: Path) -> None:
    """Call only while holding the run controller lease; never reap live peer work."""
    directory = owner.directory(workspace)
    if not directory.exists():
        return
    with FileLock(ensure_no_filesystem_links(directory / ".lock")):
        for path in sorted(directory.glob("*.json")):
            try:
                if ensure_no_filesystem_links(path).stat().st_size > 4096:
                    raise ValueError("Oversized sandbox receipt")
                receipt = SandboxReceipt.model_validate(read_json_object(path))
            except (ValueError, OSError) as exc:
                raise PolicyDeniedError(
                    "Sandbox receipt is invalid; inspect before recovery"
                ) from exc
            if (
                path.name != f"{receipt.invocation_id}.json"
                or receipt.run_id != owner.run_id
                or receipt.project_identity != _identity(owner.project_root)
                or receipt.workspace_identity != _identity(workspace)
            ):
                raise PolicyDeniedError("Sandbox receipt belongs to another execution boundary")
            _remove_owned(receipt)
            ensure_no_filesystem_links(path).unlink()


class DockerSandbox:
    def __init__(self, workspace: Path, owner: SandboxOwner | None = None) -> None:
        self.directory = owner.directory(workspace) if owner else None
        self.receipt = (
            owner.receipt(workspace)
            if owner
            else SandboxReceipt(
                invocation_id=uuid4(),
                run_id=uuid4(),
                project_identity=_identity(workspace),
                workspace_identity=_identity(workspace),
            )
        )
        self.prepared = False

    @property
    def name(self) -> str:
        return self.receipt.name

    @property
    def label_args(self) -> tuple[str, ...]:
        return tuple(
            value
            for key, label in self.receipt.labels.items()
            for value in ("--label", f"{key}={label}")
        )

    def prepare(self) -> None:
        self.receipt = self.receipt.model_copy(update={"daemon_identity": _daemon_identity()})
        if self.directory:
            self.directory.mkdir(parents=True, exist_ok=True)
            with FileLock(ensure_no_filesystem_links(self.directory / ".lock")):
                if any(self.directory.glob("*.json")):
                    raise PolicyDeniedError("Unreconciled sandbox prevents another command")
                atomic_write_json(
                    self.directory / f"{self.receipt.invocation_id}.json",
                    self.receipt.model_dump(mode="json"),
                )
        self.prepared = True

    def create(self, arguments: tuple[str, ...]) -> None:
        # Create cannot execute workspace code. A controller death during create
        # can leave a stopped container, but cannot leave an unrecorded writer.
        _docker(("create", "--name", self.name, *self.label_args, *arguments))

    def cleanup(self) -> None:
        if not self.prepared:
            return
        _remove_owned(self.receipt)
        if self.directory:
            with FileLock(ensure_no_filesystem_links(self.directory / ".lock")):
                ensure_no_filesystem_links(
                    self.directory / f"{self.receipt.invocation_id}.json"
                ).unlink()
        self.prepared = False
