from datetime import UTC, datetime, timedelta
from uuid import uuid4

from orqalis.domain.provider import (
    InvocationStatus,
    ProviderErrorCode,
    ProviderExecution,
    ProviderExecutionResult,
    ProviderUsage,
)
from orqalis.domain.timing import TimingBreakdown
from orqalis.observability.analytics import provider_statistics, statistics


def invocation(
    provider: str,
    model: str,
    status: InvocationStatus,
    milliseconds: int | None,
    usage: ProviderUsage | None = None,
    error: ProviderErrorCode | None = None,
) -> ProviderExecution:
    at = datetime(2026, 9, 26, tzinfo=UTC)
    return ProviderExecution(
        run_id=uuid4(),
        task_execution_id=uuid4(),
        actor_session_id=uuid4(),
        provider=provider,
        model=model,
        status=status,
        request_hash="fixture",
        idempotency_key=str(uuid4()),
        started_at=at,
        deadline_at=at + timedelta(minutes=1),
        completed_at=at + timedelta(milliseconds=milliseconds)
        if milliseconds is not None
        else None,
        result=ProviderExecutionResult(output={"summary": "fixture"}, usage=usage)
        if usage
        else None,
        error_code=error,
    )


def test_provider_metrics_preserve_missing_usage_and_count_all_outcomes() -> None:
    calls = (
        invocation(
            "alpha",
            "m",
            InvocationStatus.SUCCEEDED,
            100,
            ProviderUsage(
                input_tokens=0, output_tokens=0, estimated_cost_usd=0, cost_source="fixture"
            ),
        ),
        invocation("alpha", "m", InvocationStatus.FAILED, 900, error=ProviderErrorCode.TIMEOUT),
        invocation("alpha", "m", InvocationStatus.RUNNING, None),
        invocation("alpha", "m", InvocationStatus.CANCELLED, 400),
        invocation("alpha", "m", InvocationStatus.INTERRUPTED, None),
        invocation("beta", "m", InvocationStatus.SUCCEEDED, None),
        invocation("alpha", "other", InvocationStatus.SUCCEEDED, 200),
    )
    metrics = provider_statistics(calls)
    assert [(m.provider, m.model) for m in metrics] == [
        ("alpha", "m"),
        ("alpha", "other"),
        ("beta", "m"),
    ]
    alpha = metrics[0]
    assert alpha.calls == 5
    assert (alpha.succeeded, alpha.failed, alpha.running, alpha.cancelled, alpha.interrupted) == (
        1,
        1,
        1,
        1,
        1,
    )
    assert alpha.calls_with_latency == 3
    assert (alpha.p50_latency_ms, alpha.p95_latency_ms) == (400, 900)
    assert alpha.calls_with_usage == alpha.calls_with_cost == 1
    assert alpha.reported_input_tokens == alpha.reported_cost_usd == 0
    assert alpha.errors == {"timeout": 1}
    assert metrics[2].reported_input_tokens is None and metrics[2].reported_cost_usd is None
    assert metrics[2].p95_latency_ms is None
    stats = statistics((), None, {}, TimingBreakdown(), calls, 0, ())
    assert stats.providers == metrics
    assert sum(m.calls for m in metrics) == stats.provider_calls
    assert stats.first_pass_success is None


def test_percentiles_use_nearest_rank_and_exclude_running_or_invalid_durations() -> None:
    calls = tuple(invocation("alpha", "m", InvocationStatus.SUCCEEDED, n) for n in range(1, 21))
    calls += (
        invocation("alpha", "m", InvocationStatus.RUNNING, 100000),
        invocation("alpha", "m", InvocationStatus.FAILED, -100),
    )
    (metric,) = provider_statistics(calls)
    assert (metric.p50_latency_ms, metric.p95_latency_ms) == (10, 19)
    assert metric.calls == 22 and metric.calls_with_latency == 20
    assert provider_statistics(()) == ()
