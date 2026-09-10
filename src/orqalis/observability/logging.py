import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TextIO
from uuid import UUID

from opentelemetry import trace

from orqalis.domain.base import Contract, utc_now
from orqalis.security.redaction import redact


class TraceContext(Contract):
    trace_id: str | None = None
    run_id: UUID | None = None
    task_id: UUID | None = None
    actor_session_id: UUID | None = None


_context: ContextVar[TraceContext | None] = ContextVar("orqalis_trace", default=None)


@contextmanager
def trace_context(context: TraceContext) -> Iterator[None]:
    token = _context.set(context)
    try:
        yield
    finally:
        _context.reset(token)


class StructuredFormatter(logging.Formatter):
    """Allowlist fields; never serialize arbitrary extras or exception payloads."""

    def format(self, record: logging.LogRecord) -> str:
        fields = (_context.get() or TraceContext()).model_dump(mode="json")
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            fields["trace_id"] = format(span_context.trace_id, "032x")
        return json.dumps(
            {
                "timestamp": utc_now().isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": redact(record.getMessage()),
                **fields,
            }
        )


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> None:
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredFormatter())
    logger = logging.getLogger("orqalis")
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
