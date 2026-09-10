import os
import sys
from pathlib import Path

import pytest

from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.execution import ApprovedCommand, ExecutionPolicy
from orqalis.execution.commands import CommandRunner
from orqalis.execution.filesystem import ScopedFilesystem


def test_filesystem_scope_secrets_links_and_atomic_content(tmp_path: Path) -> None:
    policy = ExecutionPolicy(write_paths=("src/*.py",))
    files = ScopedFilesystem(tmp_path, policy)
    digest = files.write("src/app.py", "value = 1\n")
    assert len(digest) == 64
    assert files.read("src/app.py") == "value = 1\n"
    for path in ("../outside.py", ".Git/config", ".env", "tests/test_app.py", "src/NUL"):
        with pytest.raises(PolicyDeniedError):
            files.write(path, "unsafe")
    with pytest.raises(PolicyDeniedError):
        files.write("src/app.py", "api_key=private-value")
    original = tmp_path / "original.py"
    original.write_text("unchanged")
    os.link(original, tmp_path / "src" / "linked.py")
    with pytest.raises(PolicyDeniedError):
        files.write("src/linked.py", "changed")
    assert original.read_text() == "unchanged"


def test_commands_are_allowlisted_bounded_and_redacted(tmp_path: Path) -> None:
    script = tmp_path / "check.py"
    script.write_text("import os\nprint('ok')\nassert 'ORQALIS_DATABASE_URL' not in os.environ\n")
    command = ApprovedCommand(id="check", argv=(sys.executable, "check.py"), timeout_seconds=2)
    policy = ExecutionPolicy(
        write_paths=("*.py",), commands=(command,), command_mode="trusted_local"
    )
    runner = CommandRunner(tmp_path, policy)
    observation = runner.run(command)
    assert observation.passed and "ok" in observation.output
    script.write_text("print('api_key=private-value')\n")
    assert "private-value" not in runner.run(command).output
    script.write_text("import time\ntime.sleep(30)\n")
    assert runner.run(command).error_code == "timeout"
    script.write_text("print('x' * 2000000)\n")
    bounded = runner.run(command)
    assert bounded.error_code == "output_limit" and len(bounded.output) <= 32000
    with pytest.raises(PolicyDeniedError):
        runner.run(command.model_copy(update={"argv": ("unapproved",)}))
