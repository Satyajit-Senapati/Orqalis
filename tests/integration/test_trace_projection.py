import asyncio
import os
from pathlib import Path

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from orqalis.sdk import Orqalis
from tests.support.filesystem import filesystem_uow_factory
from tests.support.trace_fixture import execute_trace_fixture


def test_actual_parallel_repair_trace_survives_restart_and_correlates_spans(
    git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter = InMemorySpanExporter()
    tracer = TracerProvider()
    tracer.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(trace, "get_tracer", tracer.get_tracer)
    snapshot = asyncio.run(execute_trace_fixture(git_repo, tmp_path / "workers"))
    assert snapshot.statistics.max_parallel_tasks == 2
    assert snapshot.plan and snapshot.plan.version >= 2
    assert snapshot.statistics.critical_path_task_ids
    assert len(snapshot.reviews) == 2
    assert snapshot.reviews[0].result.overall == "FAIL"
    assert snapshot.reviews[-1].result.overall == "PASS"
    assert {node.kind for node in snapshot.trace} == {
        "run",
        "phase",
        "task",
        "actor",
        "model",
        "tool",
    }
    nodes = {node.id: node for node in snapshot.trace}
    assert len(nodes) == len(snapshot.trace)
    assert all(node.duration_ms is None or node.duration_ms >= 0 for node in nodes.values())
    for node in snapshot.trace:
        assert set(node.related_ids) <= nodes.keys()
        seen = {node.id}
        ancestor = node.parent_id
        while ancestor:
            assert ancestor in nodes and ancestor not in seen
            seen.add(ancestor)
            ancestor = nodes[ancestor].parent_id
    for call in snapshot.providers:
        node = nodes[f"model:{call.id}"]
        assert node.parent_id == f"actor:{call.actor_session_id}"
        assert node.related_ids == (f"task:{call.task_execution_id}",)
    for tool in snapshot.tools:
        node = nodes[f"tool:{tool.id}"]
        assert node.parent_id == f"model:{tool.provider_invocation_id}"
        assert node.task_execution_id == tool.task_execution_id
    # Every task was started under a persisted phase; no timestamp-based guess is needed.
    assert all(
        node.parent_id and node.parent_id.startswith("phase:")
        for node in snapshot.trace
        if node.kind == "task"
    )
    reopened = Orqalis(unit_of_work=filesystem_uow_factory(git_repo))
    assert reopened.snapshot(snapshot.run.id).trace == snapshot.trace
    reopened.close()
    assert "private-provider-output-sentinel" not in str(snapshot.trace)
    spans = exporter.get_finished_spans()
    provider_ids = {str(call.id) for call in snapshot.providers}
    tool_ids = {str(tool.id) for tool in snapshot.tools}
    assert {
        (span.attributes or {})["orqalis.provider_invocation_id"]
        for span in spans
        if span.name == "agent.invoke"
    } == provider_ids
    assert {
        (span.attributes or {})["orqalis.tool_invocation_id"]
        for span in spans
        if span.name == "tool.execute"
    } == tool_ids
    assert all(
        (span.attributes or {}).get("orqalis.run_id") == str(snapshot.run.id)
        for span in spans
        if span.name in {"agent.invoke", "tool.execute"}
    )
    assert "private-provider-output-sentinel" not in str(spans)
    tracer.shutdown()
    # Explicit opt-in refresh creates the frontend fixture from this verified run.
    destination = os.environ.get("ORQALIS_TRACE_SNAPSHOT_FIXTURE")
    if destination:
        Path(destination).write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
