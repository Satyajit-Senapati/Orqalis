import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.types import CallToolResult
from pydantic import BaseModel
from sqlalchemy import Engine

from orqalis.domain.acceptance import (
    CommandValidation,
    CriterionDefinition,
    GoalDraft,
    ReviewValidation,
)
from orqalis.domain.agent import AgentRole
from orqalis.domain.delivery import DeliveryPolicy, DeliveryResult
from orqalis.domain.execution import (
    ApprovedCommand,
    CriterionReview,
    ExecutionPolicy,
    ReviewResult,
    SourceCheck,
    WorkerResult,
)
from orqalis.domain.external import WorkAssignment
from orqalis.domain.projections import RunSnapshot
from orqalis.domain.provider import ProviderExecutionRequest, ProviderExecutionResult
from orqalis.mcp.policy import MCPPolicy
from orqalis.mcp.server import create_mcp
from orqalis.persistence.database import session_factory
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis

pytestmark = pytest.mark.postgres


def decoded[T: BaseModel](result: CallToolResult, model: type[T]) -> T:
    assert not result.is_error, result.content
    value = result.structured_content
    assert value is not None
    if set(value) == {"result"}:
        value = value["result"]
    return model.model_validate(value)


def test_mcp_workflow_continues_across_clients_and_enforces_server_policy(
    database: Engine,
    git_repo: Path,
    tmp_path: Path,
) -> None:
    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    sdk = Orqalis(unit_of_work=factory)
    project = sdk.initialize(git_repo)
    command = ApprovedCommand(
        id="assert-answer",
        argv=(sys.executable, "-c", "from main import answer; assert answer == 43"),
    )
    goal = GoalDraft(
        goal="Deliver answer 43 through MCP",
        scope=("main.py", "README.md"),
        definition_of_done=("Test and independent review pass",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="Answer is 43",
                validation_spec=CommandValidation(argv=command.argv),
            ),
            CriterionDefinition(
                key="AC-2",
                description="Source contains the accepted change",
                validation_spec=ReviewValidation(instructions="Inspect source"),
            ),
        ),
    )

    def respond(request: ProviderExecutionRequest) -> ProviderExecutionResult:
        assert request.role == AgentRole.REVIEWER
        assert request.acceptance
        return ProviderExecutionResult(
            output=ReviewResult(
                overall="PASS",
                criteria=tuple(
                    CriterionReview(
                        criterion_id=c.id,
                        status="PASS",
                        reason="Observed evidence/source",
                        evidence_refs=c.evidence_refs,
                        source_checks=(SourceCheck(path="main.py", contains="answer = 43"),)
                        if c.validation_spec.kind == "review"
                        else (),
                    )
                    for c in request.acceptance.criteria
                ),
                blocking_findings=(),
                non_blocking_findings=(),
            ).model_dump(mode="json")
        )

    provider = FakeProvider(respond)
    policy = MCPPolicy(
        project_id=project.id,
        workspaces_root=tmp_path / "worktrees",
        allow_work=True,
        allow_delivery=True,
        execution=ExecutionPolicy(
            write_paths=("main.py", "README.md"), commands=(command,), command_mode="trusted_local"
        ),
        delivery=DeliveryPolicy(
            documentation_path="README.md",
            author_name="Orqalis Test",
            author_email="test@orqalis.invalid",
        ),
        reviewer_provider="fixture",
    )

    async def scenario() -> None:
        server = create_mcp(sdk, policy, (provider,))
        async with Client(server, raise_exceptions=True) as first:
            names = {tool.name for tool in (await first.list_tools()).tools}
            assert {"get_project_context", "get_next_work", "report_result", "review_run"} <= names
            resource = await first.read_resource("orqalis://project")
            assert resource.contents
            context = await first.call_tool("get_project_context", {"task": "Python architecture"})
            assert not context.is_error
            created = decoded(
                await first.call_tool(
                    "start_task",
                    {
                        "request": goal.goal,
                        "branch": f"feature/mcp-{uuid4().hex[:8]}",
                        "goal": goal.model_dump(mode="json"),
                    },
                ),
                RunSnapshot,
            )
            run_id = str(created.run.id)
            assignment = decoded(
                await first.call_tool("get_next_work", {"run_id": run_id}), WorkAssignment
            )
            replay = decoded(
                await first.call_tool("get_next_work", {"run_id": run_id}), WorkAssignment
            )
            assert replay.execution.id == assignment.execution.id
            premature = await first.call_tool("review_run", {"run_id": run_id})
            assert premature.is_error
            (assignment.workspace / "main.py").write_text("answer = 43\n")
        # Another host/process shares persisted Orqalis state, not the first client's memory.
        resumed_sdk = Orqalis(unit_of_work=factory)
        async with Client(create_mcp(resumed_sdk, policy, (provider,))) as second:
            current = decoded(await second.call_tool("get_run", {"run_id": run_id}), RunSnapshot)
            assert current.run.id == created.run.id
            submitted = {
                "run_id": run_id,
                "execution_id": str(assignment.execution.id),
                "result": WorkerResult(
                    summary="Changed answer", completed=True, artifact_paths=("main.py",)
                ).model_dump(mode="json"),
            }
            result = await second.call_tool("report_result", submitted)
            assert not result.is_error, result.content
            assert not (await second.call_tool("report_result", submitted)).is_error
            forged = await second.call_tool(
                "report_result",
                {
                    **submitted,
                    "result": {
                        "summary": "Changed answer",
                        "completed": True,
                        "artifact_paths": ["main.py"],
                        "acceptance_passed": True,
                    },
                },
            )
            assert forged.is_error
            review = await second.call_tool("review_run", {"run_id": run_id})
            assert not review.is_error, review.content
            delivered = decoded(
                await second.call_tool("finalize_run", {"run_id": run_id}), DeliveryResult
            )
            assert delivered.state == "COMPLETED"
            assert provider.calls == 1
        readonly = policy.model_copy(update={"allow_work": False, "allow_delivery": False})
        async with Client(create_mcp(sdk, readonly, (provider,))) as observer:
            assert not (await observer.call_tool("get_run", {"run_id": run_id})).is_error
            assert (await observer.call_tool("get_next_work", {"run_id": run_id})).is_error
            assert (await observer.call_tool("finalize_run", {"run_id": run_id})).is_error

    asyncio.run(scenario())


def test_mcp_stdio_lifecycle_and_project_isolation(
    database: Engine,
    git_repo: Path,
    tmp_path: Path,
) -> None:
    sdk = Orqalis(unit_of_work=lambda: SQLProjectUnitOfWork(session_factory(database)))
    project = sdk.initialize(git_repo)
    policy = MCPPolicy(project_id=project.id, workspaces_root=tmp_path / "worktrees")
    config = tmp_path / "mcp-policy.json"
    config.write_text(policy.model_dump_json(), encoding="utf-8")
    parameters = StdioServerParameters(
        command=str(
            Path(sys.executable).parent / ("orqalis.exe" if os.name == "nt" else "orqalis")
        ),
        args=["mcp", "--policy", str(config)],
        env={"ORQALIS_DATABASE_URL": os.environ["ORQALIS_TEST_DATABASE_URL"]},
        cwd=Path(__file__).parents[2],
    )

    async def scenario() -> None:
        async with Client(parameters, read_timeout_seconds=30) as client:
            result = await client.call_tool("get_project", {})
            assert not result.is_error
            assert result.structured_content and result.structured_content["id"] == str(project.id)
            denied = await client.call_tool("get_run", {"run_id": str(uuid4())})
            assert denied.is_error
            assert "postgresql" not in json.dumps(denied.model_dump(mode="json"))

    asyncio.run(scenario())
