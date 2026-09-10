import asyncio
import sys
import time
from pathlib import Path

import pytest

from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.execution import ApprovedCommand, ExecutionPolicy
from orqalis.execution.cancellation import at_checkpoint
from orqalis.execution.commands import CommandRunner


def test_parent_exit_closes_descendant_pipes_and_lifetime(tmp_path: Path) -> None:
    (tmp_path / "child.py").write_text(
        "import time\nfrom pathlib import Path\nPath('ready').write_text('ready')\n"
        "time.sleep(4)\nPath('escaped').write_text('late child write')\n"
    )
    (tmp_path / "parent.py").write_text(
        "import subprocess, sys, time\nfrom pathlib import Path\n"
        "subprocess.Popen([sys.executable, 'child.py'])\n"
        "while not Path('ready').exists(): time.sleep(.01)\nprint('parent done')\n"
    )
    command = ApprovedCommand(id="parent", argv=(sys.executable, "parent.py"))
    policy = ExecutionPolicy(write_paths=("*",), commands=(command,), command_mode="trusted_local")
    before = time.monotonic()
    result = CommandRunner(tmp_path, policy).run(command)
    assert result.passed and "parent done" in result.output
    assert time.monotonic() - before < 3
    time.sleep(4.1)
    assert not (tmp_path / "escaped").exists()


def test_cancel_waits_for_command_cleanup_before_returning(tmp_path: Path) -> None:
    (tmp_path / "wait.py").write_text(
        "from pathlib import Path\nimport time\nPath('started').write_text('yes')\n"
        "time.sleep(20)\nPath('late').write_text('no')\n"
    )
    command = ApprovedCommand(id="wait", argv=(sys.executable, "wait.py"))
    policy = ExecutionPolicy(write_paths=("*",), commands=(command,), command_mode="trusted_local")

    async def scenario() -> None:
        task = asyncio.create_task(at_checkpoint(CommandRunner(tmp_path, policy).run, command))
        async with asyncio.timeout(5):
            while not (tmp_path / "started").exists():
                await asyncio.sleep(0.01)
        before = time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert time.monotonic() - before < 3
        assert not (tmp_path / "late").exists()

    asyncio.run(scenario())


def test_trusted_local_cannot_claim_readonly_isolation(tmp_path: Path) -> None:
    command = ApprovedCommand(id="review", argv=(sys.executable, "-c", "print('ok')"))
    policy = ExecutionPolicy(write_paths=("*",), commands=(command,), command_mode="trusted_local")
    with pytest.raises(PolicyDeniedError, match="Read-only"):
        CommandRunner(tmp_path, policy, read_only=True).run(command)
