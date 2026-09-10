from pathlib import Path

import pytest
from sqlalchemy import Engine

from orqalis.domain.errors import ConflictError
from orqalis.domain.events import EventType
from orqalis.persistence.database import session_factory
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork
from orqalis.sdk import Orqalis

pytestmark = pytest.mark.postgres


def test_context_failure_can_resume_same_run(
    database: Engine, git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sdk = Orqalis(unit_of_work=lambda: SQLProjectUnitOfWork(session_factory(database)))
    project = sdk.initialize(git_repo)
    with monkeypatch.context() as patch:

        def unavailable(*args: object, **kwargs: object) -> None:
            raise RuntimeError("injected memory failure")

        patch.setattr(sdk.memory, "context", unavailable)
        with pytest.raises(RuntimeError, match="injected"):
            sdk.prepare_run(project.id, "Inspect source", "feature/preparation")
    run = sdk.list_runs(project.id)[0]
    assert run.state == "BLOCKED" and run.resume_state == "CONTEXT_SYNC"
    restarted = Orqalis(unit_of_work=sdk.unit_of_work)
    with sdk.unit_of_work() as lease:
        assert lease.execution.try_run_lock(run.id)
        with pytest.raises(ConflictError, match="controller"):
            restarted.continue_preparation(run.id)
    state = restarted.continue_preparation(run.id)
    assert state.run.id == run.id and state.run.state == "ANALYZING"
    assert state.goal is None
    assert restarted.continue_preparation(run.id).last_event_sequence == state.last_event_sequence
    events = restarted.events(run.id)
    assert sum(e.event_type == EventType.MEMORY_SYNC_COMPLETED for e in events) == 1
    assert len(sdk.list_runs(project.id)) == 1
