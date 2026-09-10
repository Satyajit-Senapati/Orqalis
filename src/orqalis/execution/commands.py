import hashlib
import os
import signal
import subprocess
import sys
import threading
import time
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from orqalis.domain.artifact import ValidationObservation
from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.execution import ApprovedCommand, ExecutionPolicy
from orqalis.execution.cancellation import cancellation_requested
from orqalis.execution.windows_job import WindowsJob
from orqalis.security.redaction import safe_diagnostic

_ENV = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT"}
_OUTPUT_LIMIT = 1_000_000


def _terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,
            check=False,
            timeout=10,
        )
    else:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
    if process.poll() is None:
        process.kill()


class CommandRunner:
    """Exact configured argv, bounded capture and process-tree cleanup.

    Docker is the default isolation boundary. trusted_local is an explicit
    development fallback and cannot confine code executed by an approved command.
    """

    def __init__(self, root: Path, policy: ExecutionPolicy, *, read_only: bool = False) -> None:
        self.root = root.resolve(strict=True)
        self.policy, self.read_only = policy, read_only

    def run(
        self, command: ApprovedCommand, validator_type: str = "command", expected_exit_code: int = 0
    ) -> ValidationObservation:
        if command not in self.policy.commands:
            raise PolicyDeniedError("Command is not in the approved execution policy")
        if self.read_only and self.policy.command_mode != "docker":
            raise PolicyDeniedError("Read-only reviewer commands require Docker isolation")
        container = f"orqalis-{uuid4()}"
        docker = self.policy.command_mode == "docker"
        if docker:
            if not self.policy.container_image:
                raise PolicyDeniedError("No sandbox image configured")
            argv = (
                "docker",
                "run",
                "--rm",
                "--pull=never",
                "--name",
                container,
                "--network=none",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--memory=512m",
                "--cpus=1",
                "--pids-limit=128",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,nosuid,size=64m",
                "--mount",
                f"type=bind,source={self.root},target=/workspace"
                + (",readonly" if self.read_only else ""),
                "--workdir",
                "/workspace",
                self.policy.container_image,
                *command.argv,
            )
        else:
            argv = command.argv
        env = {key: value for key, value in os.environ.items() if key.upper() in _ENV}
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
        started = time.monotonic()
        output = bytearray()
        digest = hashlib.sha256()
        overflow = threading.Event()
        error: str | None = None
        job = WindowsJob() if os.name == "nt" else None
        try:
            with subprocess.Popen(
                argv,
                cwd=self.root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
                creationflags=(0x08000000 | 0x4) if sys.platform == "win32" else 0,
            ) as process:
                if job:
                    try:
                        job.assign_and_resume(process.pid)
                    except OSError:
                        process.kill()
                        raise
                assert process.stdout is not None

                def drain() -> None:
                    assert process.stdout is not None
                    total = 0
                    while chunk := process.stdout.read(8192):
                        total += len(chunk)
                        digest.update(chunk)
                        if len(output) < 32_000:
                            output.extend(chunk[: 32_000 - len(output)])
                        if total > _OUTPUT_LIMIT:
                            overflow.set()
                            return

                reader = threading.Thread(target=drain, daemon=True)
                reader.start()
                try:
                    while process.poll() is None:
                        if cancellation_requested():
                            error = "cancelled"
                            break
                        if overflow.is_set():
                            error = "output_limit"
                            break
                        if time.monotonic() - started > command.timeout_seconds:
                            error = "timeout"
                            break
                        time.sleep(0.02)
                finally:
                    if error:
                        _terminate(process)
                    process.wait(timeout=10)
                    # Kill descendants even when their parent exited successfully.
                    if job:
                        job.close()
                    elif sys.platform != "win32":
                        with suppress(ProcessLookupError):
                            os.killpg(process.pid, signal.SIGKILL)
                    reader.join(timeout=2)
                    if reader.is_alive():
                        error = "pipe_not_closed"
                exit_code = process.returncode
                if overflow.is_set():
                    error = "output_limit"
        except (OSError, subprocess.SubprocessError):
            exit_code, error = None, "command_failed"
        finally:
            if job:
                job.close()
            if docker:
                # Only the unique container created for this invocation can be removed.
                try:
                    subprocess.run(
                        ["docker", "rm", "--force", container],
                        env=env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                        check=False,
                        creationflags=0x08000000 if sys.platform == "win32" else 0,
                    )
                except (OSError, subprocess.SubprocessError):
                    error = error or "sandbox_cleanup_failed"
        return ValidationObservation(
            validator_type=validator_type,
            passed=error is None and exit_code == expected_exit_code,
            exit_code=exit_code,
            output=safe_diagnostic(output.decode("utf-8", errors="replace")),
            content_hash=digest.hexdigest(),
            error_code=error,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
