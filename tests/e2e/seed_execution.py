"""Create a real completed local run for browser QA; no live provider or push."""

import asyncio
import json
import os
from uuid import uuid4

from orqalis.domain.acceptance import (
    CriterionDefinition,
    FileValidation,
    GoalDraft,
    ReviewValidation,
)
from orqalis.domain.agent import AgentRole
from orqalis.domain.capabilities import ToolName
from orqalis.domain.delivery import DeliveryPolicy
from orqalis.domain.execution import (
    CriterionReview,
    ExecutionPolicy,
    ReviewResult,
    SourceCheck,
    WorkerResult,
)
from orqalis.domain.provider import (
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderToolCall,
)
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis
from tests.e2e.fixture_paths import fixture_root, pointer_path

root = fixture_root()
source = root / "mission-control-fixture"
if not (source / ".git").is_dir():
    raise SystemExit("Run tests.e2e.seed_runtime before tests.e2e.seed_execution")
repair_demo = os.environ.get("ORQALIS_QA_REPAIR") == "1"
sdk = Orqalis(root=source)
project = sdk.initialize(source)
goal = GoalDraft(
    goal="Normalize names consistently",
    scope=("main.py", "README.md"),
    constraints=("Preserve unrelated files",),
    definition_of_done=("Source assertion and independent review pass",),
    criteria=(
        CriterionDefinition(
            key="AC-1",
            description="Names trim whitespace and use lowercase",
            validation_spec=FileValidation(path="main.py", contains="value.strip().lower()"),
        ),
        CriterionDefinition(
            key="AC-2",
            description="Source remains within approved scope",
            validation_spec=ReviewValidation(instructions="Inspect normalization source"),
        ),
    ),
)
state = sdk.prepare_run(
    project.id, "Normalize names consistently", f"feature/browser-{uuid4().hex[:8]}", goal
)


def respond(request: ProviderExecutionRequest) -> ProviderExecutionResult:
    if request.role == AgentRole.DEVELOPER:
        if not request.observations:
            return ProviderExecutionResult(
                tool_calls=(
                    ProviderToolCall(
                        id="normalize",
                        name=ToolName.FILE_WRITE,
                        arguments={
                            "path": "main.py",
                            "content": (
                                "def normalize_name(value: str) -> str:\n"
                                + (
                                    "    return value.strip()\n"
                                    if repair_demo and request.task.plan_version == 1
                                    else "    return value.strip().lower()\n"
                                )
                            ),
                        },
                    ),
                )
            )
        return ProviderExecutionResult(
            output=WorkerResult(
                summary="Added lowercase normalization",
                completed=True,
                artifact_paths=("main.py",),
            ).model_dump(mode="json")
        )
    if request.role == AgentRole.REPAIR:
        return ProviderExecutionResult(
            output=WorkerResult(
                summary="Candidate does not lowercase. Repair main.py.",
                completed=True,
                artifact_paths=(),
            ).model_dump(mode="json")
        )
    assert request.acceptance is not None and request.role == AgentRole.REVIEWER
    return ProviderExecutionResult(
        output=ReviewResult(
            overall="PASS"
            if all(
                c.status == "PASS" or c.validation_spec.kind == "review"
                for c in request.acceptance.criteria
            )
            else "FAIL",
            criteria=tuple(
                CriterionReview(
                    criterion_id=c.id,
                    status="PASS"
                    if c.validation_spec.kind == "review" or c.status == "PASS"
                    else "FAIL",
                    reason="Validated current evidence and scoped source"
                    if c.status != "FAIL"
                    else "Source does not meet the lowercase normalization criterion",
                    evidence_refs=c.evidence_refs[-1:],
                    source_checks=(SourceCheck(path="main.py", contains="def normalize_name"),)
                    if c.validation_spec.kind == "review"
                    else (),
                )
                for c in request.acceptance.criteria
            ),
            blocking_findings=(),
            non_blocking_findings=(),
        ).model_dump(mode="json")
    )


async def main() -> None:
    await sdk.executor(root / "browser-worktrees", (FakeProvider(respond),)).execute(
        state.run.id,
        "fixture",
        ExecutionPolicy(write_paths=("main.py", "README.md")),
    )
    result = await sdk.delivery.finalize(
        state.run.id,
        DeliveryPolicy(
            documentation_path="README.md",
            author_name="Orqalis QA",
            author_email="qa@orqalis.invalid",
        ),
    )
    assert result.state == "COMPLETED"
    record = {
        "run_id": str(state.run.id),
        "commit": result.commit_sha,
        "fixture_root": str(root),
    }
    pointer_path("ui-repair.json" if repair_demo else "ui-completed.json").write_text(
        json.dumps(record), encoding="utf-8"
    )
    print(json.dumps(record))


asyncio.run(main())
sdk.close()
