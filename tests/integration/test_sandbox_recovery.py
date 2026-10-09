import asyncio
import subprocess
from pathlib import Path
from typing import Any

import pytest

from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.capabilities import ToolName
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.domain.execution import ApprovedCommand, ExecutionPolicy, WorkerResult
from orqalis.domain.provider import (
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderToolCall,
)
from orqalis.execution import sandbox
from orqalis.execution.sandbox import SandboxOwner
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis
from tests.support.filesystem import filesystem_uow_factory
from tests.unit.test_sandbox_lifecycle import FakeDocker


def test_tool_failure_recovery_reconciles_host_owned_receipt_before_new_attempt(
    git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk = Orqalis(unit_of_work=filesystem_uow_factory(git_repo))
    project = sdk.initialize(git_repo)
    state = sdk.prepare_run(
        project.id,
        "Check source",
        "feature/sandbox-recovery",
        GoalDraft(
            goal="Check source",
            scope=("main.py",),
            definition_of_done=("Source verified",),
            criteria=(
                CriterionDefinition(
                    key="AC-1",
                    description="Source exists",
                    validation_spec=FileValidation(path="main.py"),
                ),
            ),
        ),
    )
    command = ApprovedCommand(id="check", argv=("true",))
    policy = ExecutionPolicy(write_paths=("main.py",), commands=(command,), container_image="image")
    docker = FakeDocker()
    docker.fail_remove = True
    monkeypatch.setattr(sandbox, "_docker", docker)
    original = subprocess.Popen

    def transport(args: Any, *extra: Any, **kwargs: Any) -> subprocess.Popen[Any]:
        if args[0] == "docker":
            raise OSError("simulated start transport failure")
        return original(args, *extra, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", transport)

    def respond(request: ProviderExecutionRequest) -> ProviderExecutionResult:
        if not request.observations:
            return ProviderExecutionResult(
                tool_calls=(
                    ProviderToolCall(
                        id="run-check",
                        name=ToolName.TEST_RUN,
                        arguments={"command_id": "check"},
                    ),
                )
            )
        assert not request.observations[-1].succeeded
        return ProviderExecutionResult(
            output=WorkerResult(
                summary="Sandbox cleanup needs recovery",
                completed=False,
                artifact_paths=(),
            ).model_dump(mode="json")
        )

    provider = FakeProvider(respond)
    executor = sdk.executor(tmp_path / "workers", (provider,))
    with pytest.raises(ConflictError):
        asyncio.run(executor.execute(state.run.id, "fixture", policy))
    blocked = sdk.snapshot(state.run.id)
    assert blocked.run.state == "BLOCKED"
    attempt = blocked.attempts[-1]
    with sdk.unit_of_work() as uow:
        workspace = uow.execution.workspace(state.run.id)
        assert workspace is not None
    owner = SandboxOwner(project.repo_root, state.run.id)
    receipts = tuple(owner.directory(workspace.path).glob("*.json"))
    assert len(receipts) == 1 and not receipts[0].is_relative_to(workspace.path)
    assert docker.containers
    calls = provider.calls
    with pytest.raises(PolicyDeniedError):
        sdk.orchestrator.recover_task(
            state.run.id, attempt.id, "Inspected sandbox", "retry", acknowledge_uncertainty=True
        )
    assert sdk.snapshot(state.run.id).attempts[-1].status == "BLOCKED"
    docker.fail_remove = False
    task = sdk.orchestrator.recover_task(
        state.run.id, attempt.id, "Inspected sandbox", "retry", acknowledge_uncertainty=True
    )
    assert task.status == "READY" and not docker.containers
    assert provider.calls == calls
    assert not tuple(owner.directory(workspace.path).glob("*.json"))
