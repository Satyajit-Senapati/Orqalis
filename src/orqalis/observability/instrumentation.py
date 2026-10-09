import time
from collections.abc import Callable, Coroutine, Iterator
from contextlib import contextmanager
from functools import wraps
from typing import Any
from uuid import UUID

from opentelemetry import metrics, trace
from opentelemetry.trace import Status, StatusCode


@contextmanager
def operation(name: str) -> Iterator[None]:
    """Public operation metadata only: never prompts, commands, results or exceptions."""
    started = time.perf_counter()
    outcome = "ok"
    tracer = trace.get_tracer("orqalis.core")
    with tracer.start_as_current_span(
        name, record_exception=False, set_status_on_exception=False
    ) as span:
        try:
            yield
        except BaseException:
            outcome = "error"
            span.set_status(Status(StatusCode.ERROR))
            raise
        finally:
            span.set_attribute("orqalis.operation", name)
            span.set_attribute("orqalis.outcome", outcome)
            attributes = {"operation": name, "outcome": outcome}
            meter = metrics.get_meter("orqalis.core")
            meter.create_counter("orqalis.operations", unit="{operation}").add(1, attributes)
            meter.create_histogram("orqalis.operation.duration", unit="s").record(
                time.perf_counter() - started,
                attributes,
            )


def annotate_operation(
    *,
    run_id: UUID,
    task_id: UUID | None = None,
    actor_session_id: UUID | None = None,
    task_execution_id: UUID | None = None,
    provider_invocation_id: UUID | None = None,
    tool_invocation_id: UUID | None = None,
) -> None:
    """Attach only durable UUID identifiers, never task/provider/tool payloads."""
    span = trace.get_current_span()
    for name, value in (
        ("run_id", run_id),
        ("task_id", task_id),
        ("actor_session_id", actor_session_id),
        ("task_execution_id", task_execution_id),
        ("provider_invocation_id", provider_invocation_id),
        ("tool_invocation_id", tool_invocation_id),
    ):
        if value is not None:
            span.set_attribute(f"orqalis.{name}", str(value))


def observed[**P, R](name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorate(function: Callable[P, R]) -> Callable[P, R]:
        @wraps(function)
        def invoke(*args: P.args, **kwargs: P.kwargs) -> R:
            with operation(name):
                return function(*args, **kwargs)

        return invoke

    return decorate


def observed_async[**P, R](
    name: str,
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
    def decorate(
        function: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @wraps(function)
        async def invoke(*args: P.args, **kwargs: P.kwargs) -> R:
            with operation(name):
                return await function(*args, **kwargs)

        return invoke

    return decorate


def enable_console_telemetry() -> None:
    """CLI opt-in exporter; stderr keeps MCP stdout protocol-only."""
    import atexit
    import sys

    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import (
        ConsoleMetricExporter,
        PeriodicExportingMetricReader,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

    resource = Resource({"service.name": "orqalis"})
    tracer = TracerProvider(resource=resource)
    tracer.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter(out=sys.stderr)))
    reader = PeriodicExportingMetricReader(
        ConsoleMetricExporter(out=sys.stderr),
        export_interval_millis=60_000,
    )
    meter = MeterProvider(resource=resource, metric_readers=[reader])
    trace.set_tracer_provider(tracer)
    metrics.set_meter_provider(meter)
    atexit.register(tracer.shutdown)
    atexit.register(meter.shutdown)
