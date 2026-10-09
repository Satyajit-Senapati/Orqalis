import hashlib
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.execution import ApprovedCommand, ExecutionPolicy
from orqalis.execution import sandbox
from orqalis.execution.commands import CommandRunner
from orqalis.execution.sandbox import DockerSandbox, SandboxOwner, reconcile_sandboxes


class FakeDocker:
    def __init__(self) -> None:
        self.containers: dict[str, dict[str, Any]] = {}
        self.removed: list[str] = []
        self.fail_remove = False
        self.unavailable = False
        self.daemon_id = "fake-docker-daemon"

    def __call__(self, args: tuple[str, ...]) -> bytes:
        if self.unavailable:
            raise PolicyDeniedError("daemon unavailable")
        if args[0] == "info":
            return self.daemon_id.encode()
        if args[0] == "create":
            name = args[args.index("--name") + 1]
            labels = dict(
                args[index + 1].split("=", 1)
                for index, value in enumerate(args)
                if value == "--label"
            )
            identity = hashlib.sha256(name.encode()).hexdigest()
            self.containers[identity] = {"name": name, "labels": labels, "running": False}
            return identity.encode()
        if args[:2] == ("container", "ls"):
            name = args[args.index("--filter") + 1][len("name=^/") : -1]
            return "\n".join(
                key for key, value in self.containers.items() if value["name"] == name
            ).encode()
        if args[:2] == ("container", "inspect"):
            return json.dumps(self.containers[args[-1]]["labels"]).encode()
        if args[:2] == ("container", "rm"):
            if self.fail_remove:
                raise PolicyDeniedError("removal denied")
            self.removed.append(args[-1])
            self.containers.pop(args[-1])
            return b""
        raise AssertionError(args)


@pytest.fixture()
def boundary(tmp_path: Path) -> tuple[SandboxOwner, Path]:
    project, workspace = tmp_path / "project", tmp_path / "workspace"
    project.mkdir()
    workspace.mkdir()
    return SandboxOwner(project, uuid4()), workspace


def test_receipt_before_create_and_reconcile_by_verified_full_id(
    boundary: tuple[SandboxOwner, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, workspace = boundary
    docker = FakeDocker()
    monkeypatch.setattr(sandbox, "_docker", docker)
    session = DockerSandbox(workspace, owner)
    session.prepare()
    assert len(tuple(owner.directory(workspace).glob("*.json"))) == 1
    session.create(("image", "true"))
    identity = next(iter(docker.containers))
    reconcile_sandboxes(owner, workspace)
    reconcile_sandboxes(owner, workspace)
    assert docker.removed == [identity]
    assert not tuple(owner.directory(workspace).glob("*.json"))


@pytest.mark.parametrize("failure", ["labels", "daemon", "changed_daemon", "remove", "receipt"])
def test_recovery_fails_closed_and_retains_receipt(
    boundary: tuple[SandboxOwner, Path], monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    owner, workspace = boundary
    docker = FakeDocker()
    monkeypatch.setattr(sandbox, "_docker", docker)
    session = DockerSandbox(workspace, owner)
    session.prepare()
    session.create(("image", "true"))
    receipt = next(owner.directory(workspace).glob("*.json"))
    if failure == "labels":
        next(iter(docker.containers.values()))["labels"]["io.orqalis.run"] = str(uuid4())
    elif failure == "daemon":
        docker.unavailable = True
    elif failure == "changed_daemon":
        docker.daemon_id = "different-daemon"
    elif failure == "remove":
        docker.fail_remove = True
    else:
        raw = json.loads(receipt.read_text())
        raw["run_id"] = str(uuid4())
        receipt.write_text(json.dumps(raw))
    with pytest.raises(PolicyDeniedError):
        reconcile_sandboxes(owner, workspace)
    assert receipt.exists() and docker.containers and not docker.removed
    docker.unavailable = False
    with pytest.raises(PolicyDeniedError, match="Unreconciled"):
        DockerSandbox(workspace, owner).prepare()


def test_receipts_cannot_be_inside_mount(boundary: tuple[SandboxOwner, Path]) -> None:
    _, workspace = boundary
    with pytest.raises(PolicyDeniedError, match="outside"):
        DockerSandbox(workspace, SandboxOwner(workspace, uuid4()))


def test_command_success_cannot_hide_cleanup_failure(
    boundary: tuple[SandboxOwner, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, workspace = boundary
    docker = FakeDocker()
    docker.fail_remove = True
    monkeypatch.setattr(sandbox, "_docker", docker)

    class Process:
        pid = 12345
        returncode = 0
        stdout = io.BytesIO(b"command complete\n")

        def __enter__(self) -> "Process":
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def poll(self) -> int:
            return 0

        def wait(self, timeout: int) -> int:
            return 0

    class Job:
        def assign_and_resume(self, pid: int) -> None:
            pass

        def close(self) -> None:
            pass

    monkeypatch.setattr("orqalis.execution.commands.subprocess.Popen", lambda *a, **k: Process())
    monkeypatch.setattr("orqalis.execution.commands.WindowsJob", Job)
    monkeypatch.setattr("orqalis.execution.commands.os.killpg", lambda *a: None, raising=False)
    command = ApprovedCommand(id="check", argv=("true",))
    policy = ExecutionPolicy(write_paths=("*",), commands=(command,), container_image="image")
    result = CommandRunner(workspace, policy, sandbox_owner=owner).run(command)
    assert not result.passed and result.error_code == "sandbox_cleanup_failed"
    assert result.source_ref is not None and result.source_ref.startswith("docker:orqalis-")
    assert tuple(owner.directory(workspace).glob("*.json"))
    docker.fail_remove = False
    reconcile_sandboxes(owner, workspace)
    assert not docker.containers


@pytest.mark.parametrize("barrier", ["prepared", "created", "started"])
def test_process_death_preserves_receipt_for_independent_reconciliation(
    boundary: tuple[SandboxOwner, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    barrier: str,
) -> None:
    owner, workspace = boundary
    reached, daemon_state = tmp_path / "barrier", tmp_path / "daemon.json"
    script = r"""
import hashlib, json, sys, threading
from pathlib import Path
from uuid import UUID
from orqalis.execution import sandbox
from orqalis.execution.sandbox import DockerSandbox, SandboxOwner
project, workspace, run, marker, daemon, barrier = sys.argv[1:]
def transport(args):
    if args[0] == 'info': return b'fake-docker-daemon'
    assert args[0] == 'create'
    name=args[args.index('--name')+1]
    labels=dict(args[i+1].split('=',1) for i,v in enumerate(args) if v=='--label')
    identity=hashlib.sha256(name.encode()).hexdigest()
    Path(daemon).write_text(json.dumps({identity:{'name':name,'labels':labels,'running':False}}))
    return identity.encode()
sandbox._docker=transport
session=DockerSandbox(Path(workspace),SandboxOwner(Path(project),UUID(run)))
session.prepare()
if barrier != 'prepared':
    session.create(('image','true'))
if barrier == 'started':
    state=json.loads(Path(daemon).read_text())
    next(iter(state.values()))['running']=True
    Path(daemon).write_text(json.dumps(state))
Path(marker).write_text('ready')
threading.Event().wait()
"""
    process = subprocess.Popen(
        (
            sys.executable,
            "-c",
            script,
            str(owner.project_root),
            str(workspace),
            str(owner.run_id),
            str(reached),
            str(daemon_state),
            barrier,
        ),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        creationflags=0x08000000 if os.name == "nt" else 0,
    )
    try:
        deadline = time.monotonic() + 15
        while not reached.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert reached.exists(), "Child did not reach the deterministic crash barrier"
        process.kill()
        process.wait(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        if process.stderr:
            process.stderr.close()
    docker = FakeDocker()
    if daemon_state.exists():
        docker.containers = json.loads(daemon_state.read_text())
    assert tuple(owner.directory(workspace).glob("*.json"))
    monkeypatch.setattr(sandbox, "_docker", docker)
    reconcile_sandboxes(owner, workspace)
    assert not docker.containers
    assert len(docker.removed) == (0 if barrier == "prepared" else 1)
    assert not tuple(owner.directory(workspace).glob("*.json"))


def test_transport_nonzero_is_not_a_cleanup_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args[0], 1, stdout=b"", stderr=b"private-daemon-detail")

    monkeypatch.setattr(subprocess, "run", denied)
    with pytest.raises(PolicyDeniedError) as failure:
        sandbox._docker(("container", "rm", "--force", "owned"))
    assert "private-daemon-detail" not in str(failure.value)


def test_successful_remove_must_verify_container_absence(
    boundary: tuple[SandboxOwner, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, workspace = boundary
    docker = FakeDocker()

    def ineffective_remove(args: tuple[str, ...]) -> bytes:
        if args[:2] == ("container", "rm"):
            return b""
        return docker(args)

    monkeypatch.setattr(sandbox, "_docker", ineffective_remove)
    session = DockerSandbox(workspace, owner)
    session.prepare()
    session.create(("image", "true"))
    with pytest.raises(PolicyDeniedError, match="incomplete"):
        reconcile_sandboxes(owner, workspace)
    assert docker.containers and tuple(owner.directory(workspace).glob("*.json"))
