import asyncio
from datetime import timedelta
from pathlib import Path
from uuid import uuid5

import pytest
from sqlalchemy import Engine

from orqalis.agents.routing import CapabilityRouter
from orqalis.agents.service import AgentExecutionService
from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.base import utc_now
from orqalis.domain.errors import ConflictError
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
from orqalis.domain.task import Task
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
    sdk.orchestrator.install_plan(
        TaskPlan(
            run_id=state.run.id,
            goal_version_id=state.goal.goal.id,
            version=1,
            tasks=(task,),
            dependencies=(),
        ),
        "plan",
    )
    sdk.orchestrator.advance(state.run.id, RunState.PLANNED, "planned")
    sdk.orchestrator.advance(state.run.id, RunState.EXECUTING, "execute")
    attempt = sdk.orchestrator.start_task(state.run.id, task.id, "task")
    context = sdk.memory.context(project, "Inspect fixture")
    fake = FakeProvider(
        lambda _: ProviderExecutionResult(
            output={"summary": "Inspected"},
            usage=ProviderUsage(input_tokens=12, output_tokens=4),
        )
    )
    service = AgentExecutionService(factory, CapabilityRouter(SkillRegistry((tmp_path,)), (fake,)))

    async def invoke(key: str) -> ProviderExecutionResult:
        return await service.invoke(state.run.id, attempt.id, "fixture", context, SCHEMA, key)

    assert asyncio.run(invoke("call")) == asyncio.run(invoke("call"))
    assert fake.calls == 1
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

    # Simulate process failure after the remote call but before its result commits.
    fake.respond = lambda _: ProviderExecutionResult(output={"summary": "Observed"})

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
