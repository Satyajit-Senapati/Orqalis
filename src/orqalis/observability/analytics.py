from collections import defaultdict
from datetime import datetime
from graphlib import TopologicalSorter
from uuid import UUID

from orqalis.domain.events import Event, EventType
from orqalis.domain.execution import ReviewRecord
from orqalis.domain.plan import TaskPlan
from orqalis.domain.provider import ProviderExecution
from orqalis.domain.telemetry import RuntimeStatistics, TimelineSegment
from orqalis.domain.timing import TimingBreakdown
from orqalis.observability.timing import _ACTOR_EVENTS, _TASK_EVENTS, _TERMINAL


def timeline(events: tuple[Event, ...], now: datetime) -> tuple[TimelineSegment, ...]:
    groups: dict[tuple[str, UUID], list[Event]] = defaultdict(list)
    for event in events:
        if event.event_type in _ACTOR_EVENTS and event.actor_session_id:
            groups[("actor", event.actor_session_id)].append(event)
        if event.event_type in _TASK_EVENTS and event.task_execution_id:
            groups[("task", event.task_execution_id)].append(event)
        if event.payload.phase_execution_id and event.event_type in {
            EventType.PHASE_STARTED,
            EventType.PHASE_COMPLETED,
            EventType.PHASE_STATUS_CHANGED,
        }:
            groups[("phase", event.payload.phase_execution_id)].append(event)
    segments = []
    for (kind, entity_id), history in groups.items():
        for index, event in enumerate(history):
            if event.payload.status in _TERMINAL:
                break
            end = history[index + 1].occurred_at if index + 1 < len(history) else now
            end = max(end, event.occurred_at)
            segments.append(
                TimelineSegment(
                    kind=kind,
                    entity_id=entity_id,
                    task_id=event.task_id,
                    status=event.payload.status or "UNKNOWN",
                    started_at=event.occurred_at,
                    ended_at=end,
                    duration_ms=int((end - event.occurred_at).total_seconds() * 1000),
                )
            )
    return tuple(sorted(segments, key=lambda item: (item.started_at, item.kind, item.entity_id)))


def statistics(
    segments: tuple[TimelineSegment, ...],
    plan: TaskPlan | None,
    task_timing: dict[UUID, TimingBreakdown],
    run_timing: TimingBreakdown,
    providers: tuple[ProviderExecution, ...],
    tools_count: int,
    reviews: tuple[ReviewRecord, ...],
) -> RuntimeStatistics:
    points: dict[datetime, int] = defaultdict(int)
    total = 0
    for segment in segments:
        if segment.kind == "task" and segment.status == "RUNNING" and segment.duration_ms:
            points[segment.started_at] += 1
            points[segment.ended_at] -= 1
            total += segment.duration_ms
    concurrent, maximum = 0, 0
    for _, delta in sorted(points.items()):
        concurrent += delta
        maximum = max(maximum, concurrent)
    paths: dict[UUID, tuple[int, tuple[UUID, ...]]] = {}
    if plan:
        parents: dict[UUID, set[UUID]] = {t.id: set() for t in plan.tasks}
        for edge in plan.dependencies:
            parents[edge.task_id].add(edge.depends_on_task_id)
        for task_id in TopologicalSorter(parents).static_order():
            best = max(
                (paths[p] for p in sorted(parents[task_id])),
                default=(0, ()),
                key=lambda item: item[0],
            )
            weight = task_timing.get(task_id, TimingBreakdown()).active_ms
            paths[task_id] = (best[0] + weight, (*best[1], task_id))
    critical = max(paths.values(), default=(0, ()), key=lambda item: (item[0], len(item[1])))
    usage = [p.result.usage for p in providers if p.result]
    inputs = [u.input_tokens for u in usage if u.input_tokens is not None]
    outputs = [u.output_tokens for u in usage if u.output_tokens is not None]
    cached = [u.cached_input_tokens for u in usage if u.cached_input_tokens is not None]
    cost = [u.estimated_cost_usd for u in usage if u.estimated_cost_usd is not None]
    return RuntimeStatistics(
        max_parallel_tasks=maximum,
        mean_parallel_tasks=total / run_timing.wall_ms if run_timing.wall_ms else 0,
        critical_path_task_ids=critical[1],
        critical_path_working_ms=critical[0],
        provider_calls=len(providers),
        tool_calls=tools_count,
        calls_with_usage=sum(
            any(v is not None for v in (u.input_tokens, u.output_tokens, u.cached_input_tokens))
            for u in usage
        ),
        reported_input_tokens=sum(inputs) if inputs else None,
        reported_output_tokens=sum(outputs) if outputs else None,
        reported_cached_tokens=sum(cached) if cached else None,
        reported_cost_usd=sum(cost) if cost else None,
        calls_with_cost=len(cost),
        first_pass_success=reviews[0].result.overall == "PASS" if reviews else None,
    )
