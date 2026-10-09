"""MCP lifecycle parity uses durable Core controls, never host conversation state."""

import asyncio
from pathlib import Path
from uuid import UUID, uuid4

from mcp import Client
from mcp.types import CallToolResult
from pydantic import BaseModel

from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.execution import ExecutionPolicy
from orqalis.domain.external import WorkAssignment
from orqalis.domain.run import Run
from orqalis.domain.task import Task, TaskStatus
from orqalis.mcp.policy import MCPPolicy
from orqalis.mcp.server import create_mcp
from orqalis.sdk import Orqalis
from orqalis.tasks.history import TaskHistoryPage


def decode[T: BaseModel](result: CallToolResult, model: type[T]) -> T:
    assert not result.is_error, result.content
    value = result.structured_content
    assert value is not None
    return model.model_validate(value["result"] if set(value) == {"result"} else value)


def setup(root: Path, workspaces: Path) -> tuple[Orqalis, MCPPolicy, UUID]:
    sdk = Orqalis(root=root)
    project = sdk.initialize(root)
    goal = GoalDraft(
        goal="Inspect source through replaceable MCP clients",
        scope=("main.py",),
        definition_of_done=("Source exists",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="Source exists",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    )
    run = sdk.prepare_run(project.id, goal.goal, "feature/mcp-lifecycle", goal).run
    policy = MCPPolicy(
        project_id=project.id,
        workspaces_root=workspaces,
        allow_work=True,
        execution=ExecutionPolicy(write_paths=("main.py",), command_mode="trusted_local"),
    )
    return sdk, policy, run.id


def test_lifecycle_is_durable_idempotent_and_visible_to_replacement_client(
    git_repo: Path,
    tmp_path: Path,
) -> None:
    sdk, policy, run_id = setup(git_repo, tmp_path / "workers")
    args = {"run_id": str(run_id)}

    async def scenario() -> None:
        async with Client(create_mcp(sdk, policy)) as first:
            tools = {tool.name: tool for tool in (await first.list_tools()).tools}
            page = decode(await first.call_tool("list_task_page", {"limit": 1}), TaskHistoryPage)
            assert page.total == 1 and page.items[0].run_id == run_id
            assert page.next_cursor is None
            for name in ("pause_run", "resume_run", "cancel_run", "recover_task"):
                annotations = tools[name].annotations
                assert annotations is not None
                assert annotations.read_only_hint is False
            cancel_annotations = tools["cancel_run"].annotations
            assert cancel_annotations is not None and cancel_annotations.destructive_hint is True
            assert "idempotency_key" in tools["pause_run"].input_schema["required"]
            before = sdk.snapshot(run_id).last_event_sequence
            for key in ("", " ", "x" * 121):
                denied = await first.call_tool("pause_run", {**args, "idempotency_key": key})
                assert denied.is_error
            assert sdk.snapshot(run_id).last_event_sequence == before
            paused = decode(
                await first.call_tool(
                    "pause_run",
                    {**args, "idempotency_key": "pause-once"},
                ),
                Run,
            )
            assert paused.state == "PAUSED" and paused.resume_state == "GOAL_DEFINED"
            sequence = sdk.snapshot(run_id).last_event_sequence
            repeated = decode(
                await first.call_tool(
                    "pause_run",
                    {**args, "idempotency_key": "pause-once"},
                ),
                Run,
            )
            assert repeated.state == "PAUSED"
            assert sdk.snapshot(run_id).last_event_sequence == sequence
            assert (
                await first.call_tool(
                    "cancel_run",
                    {**args, "idempotency_key": "pause-once"},
                )
            ).is_error

        restored = Orqalis(root=git_repo)
        async with Client(create_mcp(restored, policy)) as second:
            resumed = decode(
                await second.call_tool(
                    "resume_run",
                    {**args, "idempotency_key": "resume-once"},
                ),
                Run,
            )
            assert resumed.state == "GOAL_DEFINED" and resumed.resume_state is None
            sequence = restored.snapshot(run_id).last_event_sequence
            assert not (
                await second.call_tool(
                    "resume_run",
                    {**args, "idempotency_key": "resume-once"},
                )
            ).is_error
            assert restored.snapshot(run_id).last_event_sequence == sequence
            cancelled = decode(
                await second.call_tool(
                    "cancel_run",
                    {**args, "idempotency_key": "cancel-once"},
                ),
                Run,
            )
            assert cancelled.state == "CANCELLED"
            sequence = restored.snapshot(run_id).last_event_sequence
            assert not (
                await second.call_tool(
                    "cancel_run",
                    {**args, "idempotency_key": "cancel-once"},
                )
            ).is_error
            assert restored.snapshot(run_id).last_event_sequence == sequence
            assert (
                await second.call_tool(
                    "resume_run",
                    {**args, "idempotency_key": "resume-terminal"},
                )
            ).is_error
        events = restored.events(run_id)
        for event_type in ("RUN_PAUSED", "RUN_RESUMED", "RUN_CANCELLED"):
            assert sum(event.event_type == event_type for event in events) == 1

    asyncio.run(scenario())


def test_lifecycle_enforces_readonly_and_bound_project_before_mutation(
    git_repo: Path,
    tmp_path: Path,
) -> None:
    sdk, policy, run_id = setup(git_repo, tmp_path / "workers")
    before = sdk.snapshot(run_id).last_event_sequence

    async def scenario() -> None:
        policies = (
            policy.model_copy(update={"allow_work": False}),
            policy.model_copy(update={"project_id": uuid4()}),
        )
        for denied_policy in policies:
            async with Client(create_mcp(sdk, denied_policy)) as client:
                for name in ("pause_run", "resume_run", "cancel_run", "recover_task"):
                    args = {"run_id": str(run_id), "idempotency_key": "must-not-mutate"}
                    if name == "recover_task":
                        args.update(execution_id=str(uuid4()), reason="Inspect before recovery")
                    assert (await client.call_tool(name, args)).is_error
        async with Client(create_mcp(sdk, policy)) as client:
            assert (
                await client.call_tool(
                    "cancel_run",
                    {
                        "run_id": str(uuid4()),
                        "idempotency_key": "unknown-run",
                    },
                )
            ).is_error
        assert sdk.snapshot(run_id).last_event_sequence == before

    asyncio.run(scenario())


def test_recovery_requires_inspection_lease_and_matching_receipt_across_clients(
    git_repo: Path,
    tmp_path: Path,
) -> None:
    sdk, policy, run_id = setup(git_repo, tmp_path / "workers")
    args = {"run_id": str(run_id)}
    original_goal = sdk.goals.get(run_id)

    async def scenario() -> None:
        async with Client(create_mcp(sdk, policy)) as first:
            assignment = decode(await first.call_tool("get_next_work", args), WorkAssignment)
            assert (
                await first.call_tool(
                    "pause_run",
                    {
                        **args,
                        "idempotency_key": "running-worker-denied",
                    },
                )
            ).is_error
            sdk.orchestrator.transition_task(
                run_id,
                assignment.execution.id,
                TaskStatus.WAITING,
                "worker-checkpoint",
            )
            assert not (
                await first.call_tool(
                    "pause_run",
                    {
                        **args,
                        "idempotency_key": "pause-interrupted",
                    },
                )
            ).is_error
            recovery = {
                **args,
                "execution_id": str(assignment.execution.id),
                "reason": "Prior external worker stopped; workspace inspected with no changes",
                "idempotency_key": "recover-inspected",
            }
            before = sdk.snapshot(run_id).last_event_sequence
            assert (await first.call_tool("recover_task", recovery)).is_error
            acknowledged = {**recovery, "acknowledge_uncertainty": True}
            for changed in (
                {"execution_id": str(uuid4())},
                {"reason": "password=private-recovery-sentinel"},
            ):
                denied = await first.call_tool("recover_task", {**acknowledged, **changed})
                assert denied.is_error
                assert "private-recovery-sentinel" not in str(denied.content)
            with sdk.unit_of_work() as lease:
                assert lease.execution.try_run_lock(run_id)
                assert (await first.call_tool("recover_task", acknowledged)).is_error
            assert sdk.snapshot(run_id).last_event_sequence == before
            ready = decode(await first.call_tool("recover_task", acknowledged), Task)
            assert ready.status == "READY" and ready.attempt_count == 1
            assert sdk.snapshot(run_id).run.state == "PAUSED"

        restored = Orqalis(root=git_repo)
        async with Client(create_mcp(restored, policy)) as second:
            sequence = restored.snapshot(run_id).last_event_sequence
            assert decode(await second.call_tool("recover_task", acknowledged), Task) == ready
            assert restored.snapshot(run_id).last_event_sequence == sequence
            assert (
                await second.call_tool(
                    "recover_task",
                    {
                        **acknowledged,
                        "reason": "A different recovery request",
                    },
                )
            ).is_error
            assert not (
                await second.call_tool(
                    "resume_run",
                    {
                        **args,
                        "idempotency_key": "resume-inspected",
                    },
                )
            ).is_error
            replacement = decode(await second.call_tool("get_next_work", args), WorkAssignment)
            assert replacement.execution.id != assignment.execution.id
            assert replacement.execution.attempt == 2
            assert restored.goals.get(run_id) == original_goal
            attempts = [a for a in restored.snapshot(run_id).attempts if a.task_id == ready.id]
            assert [a.status for a in attempts] == ["FAILED", "RUNNING"]

    asyncio.run(scenario())
