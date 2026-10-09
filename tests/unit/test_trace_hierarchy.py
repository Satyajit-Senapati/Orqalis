from datetime import UTC, datetime, timedelta
from uuid import uuid4

from orqalis.domain.agent import ActorSession, ActorType
from orqalis.domain.run import Run
from orqalis.domain.task import TaskExecution
from orqalis.observability.trace import trace_hierarchy


def test_historical_missing_phase_and_shared_session_do_not_invent_parents_or_timing() -> None:
    start = datetime(2026, 9, 26, tzinfo=UTC)
    run = Run(
        project_id=uuid4(),
        request="private request",
        target_branch="feature/x",
        base_commit="a" * 40,
    )
    actor = ActorSession(run_id=run.id, actor_type=ActorType.AGENT, started_at=start)
    first = TaskExecution(
        run_id=run.id, task_id=uuid4(), attempt=1, assigned_actor_session_id=actor.id
    )
    second = first.model_copy(
        update={
            "id": uuid4(),
            "attempt": 2,
            "started_at": start,
            "completed_at": start - timedelta(seconds=1),
        }
    )
    nodes = {
        node.id: node for node in trace_hierarchy(run, (), (first, second), (actor,), (), (), ())
    }
    assert nodes[f"actor:{actor.id}"].parent_id == f"run:{run.id}"
    assert nodes[f"actor:{actor.id}"].related_ids == (f"task:{first.id}", f"task:{second.id}")
    assert nodes[f"task:{first.id}"].parent_id == f"run:{run.id}"
    assert nodes[f"task:{second.id}"].parent_id == f"run:{run.id}"
    assert all(node.duration_ms is None for node in nodes.values())
    assert "private request" not in str(nodes)
