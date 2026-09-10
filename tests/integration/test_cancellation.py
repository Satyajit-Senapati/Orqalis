import asyncio
from pathlib import Path

import pytest
from sqlalchemy import Engine

from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.execution import ExecutionPolicy
from orqalis.domain.provider import ProviderExecutionRequest, ProviderExecutionResult
from orqalis.persistence.database import session_factory
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis

pytestmark = pytest.mark.postgres


def test_persisted_cancel_interrupts_provider_without_reclassifying_terminal_run(
    database: Engine,
    git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk = Orqalis(unit_of_work=lambda: SQLProjectUnitOfWork(session_factory(database)))
    project = sdk.initialize(git_repo)
    state = sdk.prepare_run(
        project.id,
        "Wait for cancellation",
        "feature/cancellation",
        GoalDraft(
            goal="Wait for cancellation",
            scope=("main.py",),
            definition_of_done=("Source checked",),
            criteria=(
                CriterionDefinition(
                    key="AC-1",
                    description="Source exists",
                    validation_spec=FileValidation(path="main.py"),
                ),
            ),
        ),
    )
    provider = FakeProvider(lambda _: ProviderExecutionResult(output={}))
    entered = asyncio.Event()

    async def slow(_: ProviderExecutionRequest) -> ProviderExecutionResult:
        entered.set()
        await asyncio.sleep(30)
        raise AssertionError("Cancelled provider must not finish")

    monkeypatch.setattr(provider, "execute", slow)

    async def scenario() -> None:
        operation = asyncio.create_task(
            sdk.executor(tmp_path / "workers", (provider,)).execute(
                state.run.id,
                "fixture",
                ExecutionPolicy(write_paths=("main.py",)),
            )
        )
        async with asyncio.timeout(10):
            await entered.wait()
        sdk.cancel(state.run.id, "cancel-from-another-client")
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(operation, timeout=5)

    asyncio.run(scenario())
    snapshot = sdk.snapshot(state.run.id)
    assert snapshot.run.state == "CANCELLED"
    assert snapshot.providers[-1].status == "CANCELLED"
    assert all(attempt.status == "CANCELLED" for attempt in snapshot.attempts)
    assert all(actor.session.completed_at for actor in snapshot.actors)
    assert snapshot.goal and snapshot.goal.criteria[0].status == "PENDING"
    with sdk.unit_of_work() as uow:
        assert uow.execution.try_run_lock(state.run.id)
