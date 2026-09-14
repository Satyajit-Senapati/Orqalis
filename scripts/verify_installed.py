"""Verify installed npm Core, MCP and UI against an explicitly disposable database.

Run with the contributor Python environment for HTTP/MCP test clients; every server
and CLI under test comes from --prefix. Set ORQALIS_TEST_DATABASE_URL (or
ORQALIS_DATABASE_URL) to an explicitly disposable database.
The caller owns database cleanup; this harness removes its temporary repository and
stops only the foreground CLI process tree verified as the UI listener owner.
POSIX smoke hosts require lsof for listener ownership inspection.
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import Any, NotRequired, Protocol, TypedDict

import httpx
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from websockets.asyncio.client import connect
from websockets.typing import Origin


def run(command: list[str], cwd: Path, env: dict[str, str]) -> str:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(
            f"Installed smoke command failed: {command[0]} (exit {result.returncode})"
        )
    return result.stdout


async def mcp_check(
    command: list[str], cwd: Path, env: dict[str, str], policy: Path, project: str, version: str
) -> int:
    parameters = StdioServerParameters(
        command=command[0], args=[*command[1:], "mcp", "--policy", str(policy)], env=env, cwd=cwd
    )
    async with Client(parameters, read_timeout_seconds=30) as client:
        assert client.server_info and client.server_info.version == version
        names = {tool.name for tool in (await client.list_tools()).tools}
        assert {"get_project", "get_project_context", "get_run", "get_plan"} <= names
        result = await client.call_tool("get_project", {})
        assert not result.is_error and result.structured_content
        assert result.structured_content["id"] == project
        context = await client.call_tool("get_project_context", {"task": "Python architecture"})
        assert not context.is_error
        return len(names)


class EventStream(Protocol):
    async def recv(self) -> str | bytes: ...


async def stream_snapshot(
    stream: EventStream, run_id: str, cursor: int
) -> tuple[dict[str, Any], int]:
    """Validate replay/live event batches through their corresponding snapshot."""
    async with asyncio.timeout(15):
        while True:
            message = json.loads(await stream.recv())
            if message["type"] == "events":
                sequences = [event["sequence"] for event in message["events"]]
                assert sequences and sequences == sorted(set(sequences))
                assert min(sequences) > cursor, "Event replay repeats or regresses its cursor"
                cursor = sequences[-1]
                continue
            assert message["type"] == "snapshot"
            snapshot: dict[str, Any] = message["snapshot"]
            assert snapshot["run"]["id"] == run_id
            assert snapshot["last_event_sequence"] == cursor, "Snapshot disagrees with event replay"
            return snapshot, cursor


async def websocket_check(base: str, run_id: str) -> None:
    endpoint = base.replace("http://", "ws://") + f"/ws/runs/{run_id}"
    async with connect(endpoint, origin=Origin(base), open_timeout=15) as stream:
        _, cursor = await stream_snapshot(stream, run_id, 0)
        async with httpx.AsyncClient(base_url=base, trust_env=False, timeout=30) as client:
            paused = await client.post(
                f"/api/runs/{run_id}/pause", json={"idempotency_key": "installed-smoke-pause"}
            )
            assert paused.status_code == 200
        before_pause = cursor
        async with asyncio.timeout(15):
            while True:
                updated, cursor = await stream_snapshot(stream, run_id, cursor)
                if updated["run"]["state"] == "PAUSED":
                    assert cursor > before_pause, "Pause did not produce persisted events"
                    break
    async with connect(
        endpoint + f"?after={cursor}", origin=Origin(base), open_timeout=15
    ) as stream:
        _, reconnected_cursor = await stream_snapshot(stream, run_id, cursor)
        assert reconnected_cursor == cursor


class UIProcessIdentity(TypedDict):
    ProcessId: int
    CommandLine: str | None
    ParentProcessId: NotRequired[int]
    ParentCommandLine: NotRequired[str | None]
    GrandparentProcessId: NotRequired[int]


def isolated_ui_executable(command: str | None) -> Path | None:
    suffix = " -I -m orqalis ui"
    if command is None or not command.endswith(suffix):
        return None
    executable = command[: -len(suffix)].strip().strip('"')
    # Resolving POSIX venv symlinks would collapse different runtimes to one base Python.
    return Path(executable).absolute() if executable else None


def verified_ui_owner(record: UIProcessIdentity, python: Path, cli_pid: int) -> int:
    """Verify the listener's isolated runtime and ancestry before cleanup."""
    executable = isolated_ui_executable(record["CommandLine"])
    assert executable is not None, "Listener is not the isolated Orqalis UI server"
    assert record["ProcessId"] > 0, "Invalid UI process ID"
    assert cli_pid > 0, "Invalid foreground CLI process ID"
    expected = python.absolute()
    if executable == expected:
        assert record.get("ParentProcessId") == cli_pid, "Listener is not owned by the CLI"
        return record["ProcessId"]
    # Windows venv redirectors launch a base-interpreter child. The managed
    # runtime must be its exact parent, and our CLI must be its grandparent.
    parent_id = record.get("ParentProcessId")
    if isolated_ui_executable(record.get("ParentCommandLine")) == expected:
        assert parent_id is not None and parent_id > 0, "Invalid UI parent process ID"
        assert record.get("GrandparentProcessId") == cli_pid, "Listener is not owned by the CLI"
        return parent_id
    raise AssertionError("Listener belongs to another runtime")


def ui_owner(port: int, python: Path, cli_pid: int, cwd: Path, env: dict[str, str]) -> int:
    """Resolve a unique listener and verify the foreground CLI owns it."""
    if sys.platform == "win32":
        script = (
            "$ErrorActionPreference='Stop'; "
            f"$owners=@(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort {port} "
            "-State Listen | Select-Object -ExpandProperty OwningProcess -Unique); "
            "if ($owners.Count -ne 1) { throw 'Expected one smoke listener' }; "
            "$ownedId=$owners[0]; "
            '$listener=Get-CimInstance Win32_Process -Filter "ProcessId = $ownedId"; '
            "$parentId=$listener.ParentProcessId; "
            '$parent=Get-CimInstance Win32_Process -Filter "ProcessId = $parentId"; '
            "$grandparentId=$parent.ParentProcessId; "
            "[pscustomobject]@{ProcessId=$listener.ProcessId; CommandLine=$listener.CommandLine; "
            "ParentProcessId=$listener.ParentProcessId; ParentCommandLine=$parent.CommandLine; "
            "GrandparentProcessId=$grandparentId} | ConvertTo-Json -Compress"
        )
        record = json.loads(
            run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], cwd, env)
        )
        return verified_ui_owner(record, python, cli_pid)
    lsof = shutil.which("lsof")
    if lsof is None:
        raise RuntimeError("Installed UI smoke needs lsof to verify its listener ownership")
    owners = run([lsof, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"], cwd, env).splitlines()
    assert len(set(owners)) == 1, "Expected one smoke listener"
    process_id = int(owners[0])
    command = run(["ps", "-ww", "-p", str(process_id), "-o", "args="], cwd, env).strip()
    parent_id = int(run(["ps", "-p", str(process_id), "-o", "ppid="], cwd, env).strip())
    return verified_ui_owner(
        {"ProcessId": process_id, "CommandLine": command, "ParentProcessId": parent_id},
        python,
        cli_pid,
    )


def stop_ui(port: int, process: subprocess.Popen[str], cwd: Path, env: dict[str, str]) -> None:
    """Stop only the CLI launched by this harness, including its server child."""
    if sys.platform == "win32":
        if process.poll() is None:
            run(["taskkill", "/PID", str(process.pid), "/T", "/F"], cwd, env)
    else:
        # Popen created a fresh session, so this process group contains only our CLI tree.
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            run(["taskkill", "/PID", str(process.pid), "/T", "/F"], cwd, env)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return
        time.sleep(0.1)
    raise RuntimeError("Owned UI process did not release its listener after shutdown")


def verify(prefix: Path, runtime: Path, workspace: Path | None = None) -> dict[str, Any]:
    database_url = os.environ.get("ORQALIS_TEST_DATABASE_URL") or os.environ.get(
        "ORQALIS_DATABASE_URL"
    )
    if not database_url:
        raise RuntimeError("ORQALIS_TEST_DATABASE_URL must name an explicitly disposable database")
    package = prefix / ("node_modules/orqalis" if os.name == "nt" else "lib/node_modules/orqalis")
    manifest = json.loads((package / "package.json").read_text(encoding="utf-8"))
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node.js is required")
    command = [node, str(package / "bin/orqalis.js")]
    env = {key: value for key, value in os.environ.items() if not key.startswith("ORQALIS_")}
    env.update(
        ORQALIS_DATABASE_URL=database_url,
        ORQALIS_RUNTIME_HOME=str(runtime),
        ORQALIS_HOST="127.0.0.1",
        NO_COLOR="1",
    )
    if os.environ.get("ORQALIS_PYTHON"):
        env["ORQALIS_PYTHON"] = os.environ["ORQALIS_PYTHON"]
    with tempfile.TemporaryDirectory(prefix="orqalis-installed-check-", dir=workspace) as temporary:
        root = Path(temporary)
        repository = root / "project"
        repository.mkdir()
        # The installed runtime and UI must not import this caller-controlled module.
        (root / "orqalis.py").write_text("raise RuntimeError('cwd module executed')\n")
        (repository / "README.md").write_text("# Fixture\nA small Python project.\n")
        (repository / "main.py").write_text("answer = 42\n")
        run(["git", "init", "-b", "main"], repository, env)
        run(["git", "add", "README.md", "main.py"], repository, env)
        run(
            [
                "git",
                "-c",
                "user.name=Orqalis QA",
                "-c",
                "user.email=qa@orqalis.invalid",
                "-c",
                f"core.hooksPath={os.devnull}",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-m",
                "Fixture baseline",
            ],
            repository,
            env,
        )
        assert run([*command, "--version"], root, env).strip() == manifest["version"]
        assert "Commands" in run([*command, "--help"], root, env)
        run([*command, "migrate"], root, env)
        doctor = json.loads(run([*command, "doctor", "--json"], root, env))
        assert doctor == {"git": True, "postgresql": True}
        project = json.loads(
            run([*command, "init", "--repo", str(repository), "--json"], root, env)
        )
        replay = json.loads(run([*command, "init", "--repo", str(repository), "--json"], root, env))
        assert replay["id"] == project["id"]
        status = json.loads(
            run([*command, "status", "--repo", str(repository), "--json"], root, env)
        )
        assert status["project"]["id"] == project["id"]
        for args in [
            ["memory", "status"],
            ["memory", "search", "architecture"],
            ["memory", "refresh"],
            ["context", "Python architecture"],
        ]:
            json.loads(run([*command, *args, "--repo", str(repository), "--json"], root, env))
        for name in ["agents", "skills"]:
            assert json.loads(run([*command, name, "--json"], root, env))
        assert json.loads(run([*command, "capabilities"], root, env))
        goal = root / "goal.json"
        goal.write_text(
            json.dumps(
                {
                    "goal": "Validate the fixture source",
                    "scope": ["main.py"],
                    "constraints": ["Keep the fixture architecture"],
                    "definition_of_done": ["Source validation is recorded"],
                    "criteria": [
                        {
                            "key": "AC-1",
                            "description": "Source exists",
                            "validation_spec": {"kind": "file", "path": "main.py"},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        prepared = json.loads(
            run(
                [
                    *command,
                    "run",
                    "Validate fixture",
                    "--repo",
                    str(repository),
                    "--branch",
                    "feature/release-smoke",
                    "--contract",
                    str(goal),
                    "--json",
                ],
                root,
                env,
            )
        )
        run_id = prepared["run"]["id"]
        assert prepared["run"]["state"] == "GOAL_DEFINED"
        policy = root / "mcp-policy.json"
        policy.write_text(
            json.dumps(
                {
                    "project_id": project["id"],
                    "workspaces_root": str(root / "worktrees"),
                    "allow_work": False,
                    "allow_delivery": False,
                }
            ),
            encoding="utf-8",
        )
        tools_count = asyncio.run(
            mcp_check(command, root, env, policy, project["id"], manifest["version"])
        )
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        env["ORQALIS_PORT"] = str(port)
        base = f"http://127.0.0.1:{port}"
        node_runtime = json.loads(
            run([node, "-p", "JSON.stringify([process.platform, process.arch])"], root, env)
        )
        fingerprint = hashlib.sha256((package / "vendor/manifest.json").read_bytes()).hexdigest()[
            :20
        ]
        runtime_path = (
            runtime / f"{manifest['version']}-{fingerprint}-{node_runtime[0]}-{node_runtime[1]}"
        )
        runtime_python = runtime_path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if sys.platform != "win32" and shutil.which("lsof") is None:
            raise RuntimeError("Installed UI smoke needs lsof to verify its listener ownership")
        log_path = root / "ui.log"
        with log_path.open("w", encoding="utf-8") as output:
            process = subprocess.Popen(
                [*command, "ui"],
                cwd=root,
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=sys.platform != "win32",
                creationflags=(
                    # Windows-only flag is absent from POSIX subprocess stubs.
                    int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP"))  # noqa: B009
                    if sys.platform == "win32"
                    else 0
                ),
            )
            try:
                with httpx.Client(base_url=base, trust_env=False, timeout=30) as client:
                    deadline = time.monotonic() + 45
                    while True:
                        if process.poll() is not None:
                            raise RuntimeError(
                                "Packaged UI command exited before serving: "
                                + log_path.read_text(encoding="utf-8")[-4000:]
                            )
                        try:
                            response = client.get("/health")
                            if response.status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        if time.monotonic() > deadline:
                            raise RuntimeError("Packaged UI startup timed out")
                        time.sleep(0.2)
                    assert response.json()["version"] == manifest["version"]
                    assert process.poll() is None, "Foreground UI command exited after startup"
                    assert ui_owner(port, runtime_python, process.pid, root, env) > 0
                    assert process.poll() is None, "Foreground UI command exited after startup"
                    assert run([*command, "ui"], root, env).strip() == base
                    assert process.poll() is None, "UI reuse stopped the foreground session"
                    page = client.get("/")
                    assert page.status_code == 200 and '<div id="root"></div>' in page.text
                    assets = set(re.findall(r'(?:src|href)="(/assets/[^"]+)"', page.text))
                    assert assets
                    for asset in assets:
                        response = client.get(asset)
                        assert response.status_code == 200 and response.content
                    for path in [f"/runs/{run_id}", f"/runs/{run_id}"]:
                        assert client.get(path).text == page.text
                    snapshot = client.get(f"/api/runs/{run_id}").json()
                    assert snapshot["run"]["id"] == run_id and snapshot["actors"]
                    assert any(p["id"] == project["id"] for p in client.get("/api/projects").json())
                    assert (
                        client.get("/openapi.json").json()["info"]["version"] == manifest["version"]
                    )
                    asyncio.run(websocket_check(base, run_id))
                    assert process.poll() is None, "Foreground UI command exited during checks"
            finally:
                stop_ui(port, process, root, env)
        with socket.socket() as probe:
            assert probe.connect_ex(("127.0.0.1", port)) != 0, "UI port remains open after shutdown"
        return {
            "version": manifest["version"],
            "project_id": project["id"],
            "run_id": run_id,
            "mcp_tools": tools_count,
            "checks": {
                name: "PASS"
                for name in [
                    "version_help",
                    "migrate_doctor",
                    "fresh_project_idempotent_init",
                    "status_memory_context",
                    "agent_skill_catalog",
                    "explicit_goal_run",
                    "mcp_stdio_version_context",
                    "packaged_ui_host",
                    "ui_cold_start_hostile_cwd",
                    "ui_command_reuse",
                    "ui_foreground_session",
                    "static_assets",
                    "direct_route_refresh",
                    "api_schema",
                    "websocket_order_reconnect",
                    "owned_process_shutdown",
                    "cwd_import_isolation",
                ]
            },
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument(
        "--workspace", type=Path, help="Existing external temporary parent directory"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(
        args.prefix.resolve(),
        args.runtime.resolve(),
        args.workspace.resolve() if args.workspace else None,
    )
    encoded = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
