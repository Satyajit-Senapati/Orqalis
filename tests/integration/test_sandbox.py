import os
from pathlib import Path

import pytest

from orqalis.domain.execution import ApprovedCommand, ExecutionPolicy
from orqalis.execution.commands import CommandRunner


@pytest.mark.docker
def test_docker_workspace_network_and_readonly_root(tmp_path: Path) -> None:
    image = os.environ.get("ORQALIS_TEST_SANDBOX_IMAGE")
    if not image:
        pytest.skip("Set ORQALIS_TEST_SANDBOX_IMAGE to an already available sandbox image")
    (tmp_path / "input.txt").write_text("sandbox fixture")
    command = ApprovedCommand(
        id="sandbox-probe",
        argv=(
            "sh",
            "-c",
            "cat /workspace/input.txt; "
            "test -r /workspace/input.txt && "
            "! touch /etc/orqalis-readonly-probe && "
            "test $(ls /sys/class/net | wc -l) -eq 1",
        ),
        timeout_seconds=30,
    )
    policy = ExecutionPolicy(
        write_paths=("result.txt",), commands=(command,), container_image=image
    )
    result = CommandRunner(tmp_path, policy).run(command)
    assert result.passed, result
    assert "sandbox fixture" in result.output

    readonly_command = ApprovedCommand(
        id="readonly-probe",
        argv=("sh", "-c", "test -r /workspace/input.txt && ! touch /workspace/forbidden.txt"),
        timeout_seconds=30,
    )
    readonly_policy = policy.model_copy(update={"commands": (readonly_command,)})
    readonly = CommandRunner(tmp_path, readonly_policy, read_only=True).run(readonly_command)
    assert readonly.passed, readonly
    assert not (tmp_path / "forbidden.txt").exists()
