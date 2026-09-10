import asyncio

import pytest
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from orqalis.observability.instrumentation import observed, observed_async


def test_spans_and_metrics_exclude_exception_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    exporter = InMemorySpanExporter()
    tracer = TracerProvider()
    tracer.add_span_processor(SimpleSpanProcessor(exporter))
    reader = InMemoryMetricReader()
    meter = MeterProvider(metric_readers=[reader])
    monkeypatch.setattr(trace, "get_tracer", tracer.get_tracer)
    monkeypatch.setattr(metrics, "get_meter", meter.get_meter)

    @observed("fixture.sync")
    def outer() -> None:
        assert trace.get_current_span().get_span_context().is_valid
        asyncio.run(inner())

    @observed_async("fixture.async")
    async def inner() -> None:
        raise RuntimeError("api_key=must-never-leak private chain_of_thought")

    with pytest.raises(RuntimeError):
        outer()
    spans = exporter.get_finished_spans()
    assert len(spans) == 2 and spans[0].parent == spans[1].context
    assert all(span.status.status_code.name == "ERROR" for span in spans)
    assert all(not span.events and span.status.description is None for span in spans)
    assert "must-never-leak" not in str(spans)
    data = reader.get_metrics_data()
    assert data is not None
    names = {
        m.name for r in data.resource_metrics for scope in r.scope_metrics for m in scope.metrics
    }
    assert names == {"orqalis.operations", "orqalis.operation.duration"}
    assert "private" not in str(data)
    tracer.shutdown()
    meter.shutdown()
