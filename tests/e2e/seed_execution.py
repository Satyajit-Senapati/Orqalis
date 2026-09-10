"""Create a real completed local run for browser QA; no live provider or push."""

import asyncio
import json
from pathlib import Path
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

root = Path(__file__).resolve().parents[2] / ".tools"
source = root / "mission-control-fixture"
sdk = Orqalis()
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
                                "    return value.strip().lower()\n"
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
    assert request.acceptance is not None and request.role == AgentRole.REVIEWER
    return ProviderExecutionResult(
        output=ReviewResult(
            overall="PASS",
            criteria=tuple(
                CriterionReview(
                    criterion_id=c.id,
                    status="PASS",
                    reason="Validated evidence and scoped source",
                    evidence_refs=c.evidence_refs,
                    source_checks=(SourceCheck(path="main.py", contains="value.strip().lower()"),)
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
    record = {"run_id": str(state.run.id), "commit": result.commit_sha}
    (root / "ui-completed.json").write_text(json.dumps(record))
    print(json.dumps(record))


asyncio.run(main())
sdk.close()
