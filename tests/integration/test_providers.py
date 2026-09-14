import asyncio
from datetime import timedelta
from pathlib import Path
from uuid import uuid4, uuid5

import pytest
from sqlalchemy import Engine

from orqalis.agents.routing import CapabilityRouter
from orqalis.agents.service import AgentExecutionService
from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.agent import AgentRole
from orqalis.domain.base import utc_now
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.domain.events import EventType
from orqalis.domain.plan import TaskPlan
from orqalis.domain.provider import (
    InvocationStatus,
    ProviderErrorCode,
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderUsage,
)
from orqalis.domain.run import RunState
from orqalis.domain.task import Task, TaskStatus
from orqalis.persistence.database import session_factory
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork
from orqalis.providers.errors import ProviderError
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis
from orqalis.skills.registry import SkillRegistry
from tests.unit.test_providers import SCHEMA

pytestmark = pytest.mark.postgres


def test_provider_durable_outcomes_idempotency_failure_and_cancellation(
    database: Engine,
    git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    sdk = Orqalis(unit_of_work=factory)
    project = sdk.initialize(git_repo)
    draft = GoalDraft(
        goal="Inspect fixture",
        scope=("main.py",),
        definition_of_done=("Observed evidence",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="Main exists",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    )
    state = sdk.prepare_run(project.id, "Inspect fixture", "feature/provider", draft)
    assert state.goal is not None
    task = Task(
        run_id=state.run.id,
        description="Inspect fixture",
        expected_outcome="Summary",
        validation_method="file assertion",
        acceptance_criterion_ids=(state.goal.criteria[0].id,),
    )
    tester_task = task.model_copy(update={"id": uuid4(), "preferred_role": AgentRole.TESTER})
    sdk.orchestrator.install_plan(
        TaskPlan(
            run_id=state.run.id,
            goal_version_id=state.goal.goal.id,
            version=1,
            tasks=(task, tester_task),
            dependencies=(),
        ),
        "plan",
    )
    sdk.orchestrator.advance(state.run.id, RunState.PLANNED, "planned")
    sdk.orchestrator.advance(state.run.id, RunState.EXECUTING, "execute")
    context = sdk.memory.context(project, "Inspect fixture")
    fake = FakeProvider(
        lambda _: ProviderExecutionResult(
            output={"summary": "Inspected"},
            usage=ProviderUsage(input_tokens=12, output_tokens=4),
        )
    )
    service = AgentExecutionService(factory, CapabilityRouter(SkillRegistry((tmp_path,)), (fake,)))
    tester_attempt = sdk.orchestrator.start_task(state.run.id, tester_task.id, "tester-task")
    with pytest.raises(PolicyDeniedError, match="deterministic service"):
        asyncio.run(
            service.invoke(state.run.id, tester_attempt.id, "fixture", context, SCHEMA, "tester")
        )
    assert fake.calls == 0
    sdk.orchestrator.transition_task(
        state.run.id, tester_attempt.id, TaskStatus.SUCCEEDED, "tester-finished"
    )
    attempt = sdk.orchestrator.start_task(state.run.id, task.id, "task")

    async def invoke(key: str) -> ProviderExecutionResult:
        return await service.invoke(state.run.id, attempt.id, "fixture", context, SCHEMA, key)

    assert asyncio.run(invoke("call")) == asyncio.run(invoke("call"))
    assert fake.calls == 1
    projected = sdk.snapshot(state.run.id).providers[0]
    assert projected.context_memory_ids == tuple(item.item.id for item in context.items)
    assert projected.context_summary and projected.context_summary.startswith("Context:")
    assert "instructions" not in projected.model_dump_json()
    assert "output_schema" not in projected.model_dump_json()
    with factory() as uow:
        records = uow.providers.list(state.run.id)
        assert records[0].status == InvocationStatus.SUCCEEDED
        assert records[0].result and records[0].result.usage.input_tokens == 12
        saved_run = uow.runs.get(state.run.id)
        assert saved_run and saved_run.state == RunState.EXECUTING
        actor = next(
            item
            for item in uow.runtime.actors(state.run.id)
            if item.id == attempt.assigned_actor_session_id
        )
        assert actor.provider == "fixture"
    with pytest.raises(ConflictError):
        asyncio.run(
            service.invoke(state.run.id, attempt.id, "fixture", context, {"type": "object"}, "call")
        )

    fake.respond = lambda _: ProviderExecutionResult(output={"summary": "api_key=unsafe-value"})
    with pytest.raises(ProviderError) as caught:
        asyncio.run(invoke("invalid"))
    assert caught.value.error_code == ProviderErrorCode.INVALID_OUTPUT
    with factory() as uow:
        failed = uow.providers.get(uuid5(state.run.id, "provider:invalid"))
        assert failed and failed.result is None and failed.status == InvocationStatus.FAILED
        assert "unsafe-value" not in failed.model_dump_json()

    async def cancellation() -> None:
        started = asyncio.Event()
        waiting = asyncio.Event()

        class WaitingProvider:
            descriptor = fake.descriptor

            async def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
                started.set()
                await waiting.wait()
                return ProviderExecutionResult(output={"summary": "Late response"})

        current = AgentExecutionService(
            factory, CapabilityRouter(SkillRegistry((tmp_path,)), (WaitingProvider(),))
        )
        worker = asyncio.create_task(
            current.invoke(state.run.id, attempt.id, "fixture", context, SCHEMA, "cancel")
        )
        await started.wait()
        with pytest.raises(ConflictError):
            await current.invoke(state.run.id, attempt.id, "fixture", context, SCHEMA, "cancel")
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker

    asyncio.run(cancellation())
    with factory() as uow:
        cancelled = uow.providers.get(uuid5(state.run.id, "provider:cancel"))
        assert cancelled and cancelled.status == InvocationStatus.CANCELLED
        events = uow.events.list(state.run.id)
        assert sum(e.event_type == EventType.PROVIDER_INVOCATION_STARTED for e in events) == 3
        assert sum(e.event_type == EventType.PROVIDER_INVOCATION_COMPLETED for e in events) == 3

    # Auto-routing persists the concrete adapter rather than the selector name.
    fake.respond = lambda _: ProviderExecutionResult(output={"summary": "Observed"})
    fake.descriptor = fake.descriptor.model_copy(update={"auto_selectable": True})
    auto_result = asyncio.run(
        service.invoke(state.run.id, attempt.id, "auto", context, SCHEMA, "auto-route")
    )
    assert auto_result.output == {"summary": "Observed"}
    with factory() as uow:
        selected = uow.providers.get(uuid5(state.run.id, "provider:auto-route"))
        assert selected and selected.provider == "fixture"

    # Simulate process failure after the remote call but before its result commits.
    def crash_before_commit(*args: object) -> None:
        raise RuntimeError("simulated process interruption")

    with monkeypatch.context() as patch:
        patch.setattr(service, "_finish", crash_before_commit)
        with pytest.raises(RuntimeError):
            asyncio.run(invoke("interrupted"))
    before_recovery = fake.calls
    service.clock = lambda: utc_now() + timedelta(hours=1)
    with pytest.raises(ProviderError) as recovery:
        asyncio.run(invoke("interrupted"))
    assert recovery.value.error_code == ProviderErrorCode.INTERRUPTED
    assert fake.calls == before_recovery
    with factory() as uow:
        interrupted = uow.providers.get(uuid5(state.run.id, "provider:interrupted"))
        assert interrupted and interrupted.status == InvocationStatus.INTERRUPTED
