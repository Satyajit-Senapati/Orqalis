"""Rebuildable, payload-free local trace hierarchy from persisted runtime identities."""

from collections import defaultdict
from datetime import datetime
from uuid import UUID

from orqalis.domain.agent import ActorSession
from orqalis.domain.events import Event, EventType
from orqalis.domain.execution import ToolInvocation
from orqalis.domain.provider import ProviderExecution
from orqalis.domain.run import Run
from orqalis.domain.task import TaskExecution
from orqalis.domain.telemetry import TraceNode
from orqalis.domain.timing import PhaseExecution


def _duration(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None or end < start:
        return None
    return int((end - start).total_seconds() * 1000)


def trace_hierarchy(
    run: Run,
    phases: tuple[PhaseExecution, ...],
    attempts: tuple[TaskExecution, ...],
    actors: tuple[ActorSession, ...],
    providers: tuple[ProviderExecution, ...],
    tools: tuple[ToolInvocation, ...],
    events: tuple[Event, ...],
) -> tuple[TraceNode, ...]:
    root = f"run:{run.id}"
    known_phases = {phase.id for phase in phases}
    phase_by_attempt: dict[UUID, UUID] = {}
    active_phase: UUID | None = None
    for event in sorted(events, key=lambda item: item.sequence):
        phase_id = event.payload.phase_execution_id
        if event.event_type == EventType.PHASE_STARTED and phase_id in known_phases:
            active_phase = phase_id
        elif event.event_type == EventType.PHASE_COMPLETED and active_phase == phase_id:
            active_phase = None
        if event.event_type == EventType.TASK_STARTED and event.task_execution_id and active_phase:
            phase_by_attempt.setdefault(event.task_execution_id, active_phase)
    by_actor: dict[UUID, list[TaskExecution]] = defaultdict(list)
    by_attempt = {attempt.id: attempt for attempt in attempts}
    for attempt in attempts:
        by_actor[attempt.assigned_actor_session_id].append(attempt)
    known_actors = {actor.id for actor in actors}
    known_providers = {provider.id for provider in providers}
    nodes = [
        TraceNode(
            id=root,
            entity_id=run.id,
            kind="run",
            label="Run",
            status=run.state,
            started_at=run.started_at,
            completed_at=run.completed_at,
            duration_ms=_duration(run.started_at, run.completed_at),
        )
    ]
    for phase in phases:
        nodes.append(
            TraceNode(
                id=f"phase:{phase.id}",
                entity_id=phase.id,
                kind="phase",
                parent_id=root,
                label=f"{phase.phase.value} iteration {phase.iteration}",
                status=phase.status,
                started_at=phase.started_at,
                completed_at=phase.completed_at,
                duration_ms=_duration(phase.started_at, phase.completed_at),
            )
        )
    for attempt in attempts:
        attempt_phase = phase_by_attempt.get(attempt.id)
        nodes.append(
            TraceNode(
                id=f"task:{attempt.id}",
                entity_id=attempt.id,
                kind="task",
                parent_id=f"phase:{attempt_phase}" if attempt_phase else root,
                label=f"Task attempt {attempt.attempt}",
                status=attempt.status,
                started_at=attempt.started_at,
                completed_at=attempt.completed_at,
                duration_ms=_duration(attempt.started_at, attempt.completed_at),
                task_id=attempt.task_id,
                task_execution_id=attempt.id,
                actor_session_id=attempt.assigned_actor_session_id,
            )
        )
    for actor in actors:
        assigned = sorted(by_actor.get(actor.id, ()), key=lambda item: (item.attempt, item.id))
        # A session shared by multiple attempts is linked, never falsely duplicated.
        parent = f"task:{assigned[0].id}" if len(assigned) == 1 else root
        nodes.append(
            TraceNode(
                id=f"actor:{actor.id}",
                entity_id=actor.id,
                kind="actor",
                parent_id=parent,
                related_ids=tuple(f"task:{attempt.id}" for attempt in assigned)
                if len(assigned) > 1
                else (),
                label=actor.role.value if actor.role else "Orchestrator",
                status=actor.status,
                started_at=actor.started_at,
                completed_at=actor.completed_at,
                duration_ms=_duration(actor.started_at, actor.completed_at),
                actor_session_id=actor.id,
            )
        )
    for provider in providers:
        provider_attempt = by_attempt.get(provider.task_execution_id)
        nodes.append(
            TraceNode(
                id=f"model:{provider.id}",
                entity_id=provider.id,
                kind="model",
                parent_id=f"actor:{provider.actor_session_id}"
                if provider.actor_session_id in known_actors
                else root,
                related_ids=(f"task:{provider_attempt.id}",) if provider_attempt else (),
                label="Model call",
                status=provider.status,
                started_at=provider.started_at,
                completed_at=provider.completed_at,
                duration_ms=_duration(provider.started_at, provider.completed_at),
                task_id=provider_attempt.task_id if provider_attempt else None,
                task_execution_id=provider.task_execution_id,
                actor_session_id=provider.actor_session_id,
                provider_invocation_id=provider.id,
            )
        )
    for tool in tools:
        tool_attempt = by_attempt.get(tool.task_execution_id)
        nodes.append(
            TraceNode(
                id=f"tool:{tool.id}",
                entity_id=tool.id,
                kind="tool",
                parent_id=f"model:{tool.provider_invocation_id}"
                if tool.provider_invocation_id in known_providers
                else root,
                related_ids=(f"task:{tool_attempt.id}",) if tool_attempt else (),
                label=tool.tool.value,
                status=tool.status,
                started_at=tool.started_at,
                completed_at=tool.completed_at,
                duration_ms=_duration(tool.started_at, tool.completed_at),
                task_id=tool_attempt.task_id if tool_attempt else None,
                task_execution_id=tool.task_execution_id,
                actor_session_id=tool.actor_session_id,
                provider_invocation_id=tool.provider_invocation_id,
            )
        )
    return tuple(nodes)
