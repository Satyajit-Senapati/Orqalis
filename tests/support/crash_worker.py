"""Child process for the offline hard-kill recovery matrix.

The parent kills this process only after an explicit persisted/effect barrier.
No signal handler or exception cleanup is used to simulate the interruption.
"""

import asyncio
import json
import sys
import threading
from pathlib import Path
from typing import Any
from uuid import UUID

from orqalis.domain.agent import AgentRole
from orqalis.domain.capabilities import ToolName
from orqalis.domain.delivery import DeliveryPolicy
from orqalis.domain.execution import CriterionReview, ExecutionPolicy, ReviewResult, WorkerResult
from orqalis.domain.provider import (
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderToolCall,
)
from orqalis.domain.run import RunState
from orqalis.execution.filesystem import ScopedFilesystem
from orqalis.persistence.filesystem.io import atomic_write_json
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis
from tests.support.filesystem import filesystem_uow_factory


def main() -> None:
    root, worktrees, run_text, phase, marker_text, audit_text = sys.argv[1:]
    run_id = UUID(run_text)
    marker, audit = Path(marker_text), Path(audit_text)
    sdk = Orqalis(unit_of_work=filesystem_uow_factory(Path(root)))

    def log(kind: str, identity: str) -> None:
        with audit.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"kind": kind, "identity": identity}) + "\n")
            stream.flush()

    def barrier(value: object = None) -> None:
        atomic_write_json(marker, {"phase": phase, "value": value})
        threading.Event().wait()

    def respond(request: ProviderExecutionRequest) -> ProviderExecutionResult:
        log("provider", str(request.invocation_id))
        if request.role == AgentRole.DEVELOPER:
            if not request.observations:
                return ProviderExecutionResult(
                    tool_calls=(
                        ProviderToolCall(
                            id="write-main",
                            name=ToolName.FILE_WRITE,
                            arguments={"path": "main.py", "content": "answer = 43\n"},
                        ),
                    )
                )
            return ProviderExecutionResult(
                output=WorkerResult(
                    completed=True,
                    summary="Changed answer",
                    artifact_paths=("main.py",),
                ).model_dump(mode="json")
            )
        if request.role == AgentRole.REPAIR:
            return ProviderExecutionResult(
                output=WorkerResult(
                    completed=True,
                    summary="Diagnosis complete",
                    artifact_paths=(),
                ).model_dump(mode="json")
            )
        assert request.role == AgentRole.REVIEWER and request.acceptance
        # One deliberate review failure exercises a real bounded repair cycle.
        passed = sdk.snapshot(run_id).run.repair_iteration > 0
        return ProviderExecutionResult(
            output=ReviewResult(
                overall="PASS" if passed else "FAIL",
                criteria=tuple(
                    CriterionReview(
                        criterion_id=criterion.id,
                        status="PASS" if passed else "FAIL",
                        reason="Verified repair" if passed else "Require one deterministic repair",
                        evidence_refs=criterion.evidence_refs[-1:],
                        source_checks=(),
                    )
                    for criterion in request.acceptance.criteria
                ),
                blocking_findings=(),
                non_blocking_findings=(),
            ).model_dump(mode="json")
        )

    executor = sdk.executor(Path(worktrees), (FakeProvider(respond),))
    policy = ExecutionPolicy(write_paths=("main.py", "README.md"))
    delivery = DeliveryPolicy(
        documentation_path="README.md",
        author_name="Orqalis Crash Test",
        author_email="crash@orqalis.invalid",
    )

    original_write = ScopedFilesystem.write

    def write(files: ScopedFilesystem, path: str, content: str) -> str:
        result = original_write(files, path, content)
        log("write", path)
        if phase == "documentation" and path == "README.md":
            # Effect is atomic; its artifact receipt has not been committed yet.
            barrier(result)
        return result

    ScopedFilesystem.write = write  # type: ignore[method-assign,assignment]

    if phase in {"planning", "repair"}:
        method = "install_plan" if phase == "planning" else "install_repair_plan"
        install = getattr(sdk.orchestrator, method)

        def installed(*args: Any, **kwargs: Any) -> Any:
            result = install(*args, **kwargs)
            barrier(result.plan_version)
            return result

        setattr(sdk.orchestrator, method, installed)
    elif phase == "agent":
        execute = executor.worker.execute

        async def finished(*args: Any, **kwargs: Any) -> Any:
            result = await execute(*args, **kwargs)
            barrier()
            return result

        executor.worker.execute = finished  # type: ignore[method-assign]
    elif phase == "tool":
        execute_tool = executor.worker.tools.execute

        def tool_finished(*args: Any, **kwargs: Any) -> Any:
            result = execute_tool(*args, **kwargs)
            barrier(result.call_id)
            return result

        executor.worker.tools.execute = tool_finished  # type: ignore[method-assign]
    elif phase == "review":
        record = executor.reviews.record

        def reviewed(*args: Any, **kwargs: Any) -> Any:
            result = record(*args, **kwargs)
            barrier(str(result.id))
            return result

        executor.reviews.record = reviewed  # type: ignore[method-assign]
    elif phase in {"git_prepare", "git_attach"}:
        operation = "create_commit" if phase == "git_prepare" else "attach"
        git_operation = getattr(sdk.delivery.commits.operations, operation)

        def git_finished(*args: Any, **kwargs: Any) -> Any:
            result = git_operation(*args, **kwargs)
            barrier(result if phase == "git_prepare" else args[1])
            return result

        setattr(sdk.delivery.commits.operations, operation, git_finished)

    current = sdk.snapshot(run_id).run.state
    if current in {
        RunState.GOAL_DEFINED,
        RunState.PLANNED,
        RunState.EXECUTING,
        RunState.INTEGRATING,
        RunState.TESTING,
        RunState.REVIEWING,
        RunState.REPAIR_PLANNING,
    }:
        result = asyncio.run(executor.execute(run_id, "fixture", policy))
        assert result.review and result.review.result.overall == "PASS"
    delivered = asyncio.run(sdk.delivery.finalize(run_id, delivery))
    assert asyncio.run(sdk.delivery.finalize(run_id, delivery)) == delivered
    assert phase == "complete", f"Missed requested crash barrier: {phase}"
    atomic_write_json(marker, delivered.model_dump(mode="json"))


if __name__ == "__main__":
    main()
