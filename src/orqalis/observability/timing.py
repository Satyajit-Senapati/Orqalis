from datetime import datetime
from typing import Protocol
from uuid import UUID

from orqalis.domain.events import Event, EventType
from orqalis.domain.timing import TimingBreakdown

_ACTOR_EVENTS = {EventType.ACTOR_STARTED, EventType.ACTOR_STATUS_CHANGED, EventType.ACTOR_COMPLETED}
_TASK_EVENTS = {
    EventType.TASK_STARTED,
    EventType.TASK_WAITING,
    EventType.TASK_BLOCKED,
    EventType.TASK_COMPLETED,
    EventType.TASK_FAILED,
    EventType.TASK_CANCELLED,
}
_RUN_EVENTS = {
    EventType.RUN_STARTED,
    EventType.RUN_STATE_CHANGED,
    EventType.RUN_PAUSED,
    EventType.RUN_RESUMED,
    EventType.RUN_BLOCKED,
    EventType.RUN_CANCELLED,
    EventType.RUN_FAILED,
    EventType.RUN_COMPLETED,
}
_ACTIVE = {
    "WORKING",
    "RUNNING",
    "CONTEXT_SYNC",
    "ANALYZING",
    "GOAL_DEFINED",
    "PLANNED",
    "EXECUTING",
    "INTEGRATING",
    "TESTING",
    "REVIEWING",
    "REPAIR_PLANNING",
    "CHANGE_GUARD",
    "DOCUMENTING",
    "DELIVERY_VALIDATION",
    "COMMITTING",
    "PUSHING",
    "MEMORY_FINALIZATION",
}
_WAITING = {"WAITING", "WAITING_FOR_DEPENDENCY", "PAUSED", "READY", "STARTING"}
_BLOCKED = {"BLOCKED", "HUMAN_REVIEW_REQUIRED"}
_TERMINAL = {"SUCCEEDED", "FAILED", "COMPLETE", "COMPLETED", "CANCELLED", "SKIPPED"}


def intervals(events: tuple[Event, ...], now: datetime) -> TimingBreakdown:
    if not events:
        return TimingBreakdown()
    counters = {"active_ms": 0, "waiting_ms": 0, "blocked_ms": 0, "idle_ms": 0}
    wall = 0
    for index, event in enumerate(events):
        status = event.payload.status
        if status in _TERMINAL:
            break
        end = events[index + 1].occurred_at if index + 1 < len(events) else now
        duration = max(0, int((end - event.occurred_at).total_seconds() * 1000))
        wall += duration
        category = (
            "active_ms"
            if status in _ACTIVE
            else "waiting_ms"
            if status in _WAITING
            else "blocked_ms"
            if status in _BLOCKED
            else "idle_ms"
        )
        counters[category] += duration
    return TimingBreakdown(wall_ms=wall, **counters)


class TimingProjectionService(Protocol):
    def actor(
        self, events: tuple[Event, ...], actor_id: UUID, now: datetime
    ) -> TimingBreakdown: ...
    def task(
        self, events: tuple[Event, ...], execution_id: UUID, now: datetime
    ) -> TimingBreakdown: ...
    def run(self, events: tuple[Event, ...], now: datetime) -> TimingBreakdown: ...

    def phase(
        self, events: tuple[Event, ...], phase_id: UUID, now: datetime
    ) -> TimingBreakdown: ...


class EventTimingProjection:
    def actor(self, events: tuple[Event, ...], actor_id: UUID, now: datetime) -> TimingBreakdown:
        return intervals(
            tuple(
                event
                for event in events
                if event.actor_session_id == actor_id and event.event_type in _ACTOR_EVENTS
            ),
            now,
        )

    def task(self, events: tuple[Event, ...], execution_id: UUID, now: datetime) -> TimingBreakdown:
        return intervals(
            tuple(
                event
                for event in events
                if event.task_execution_id == execution_id and event.event_type in _TASK_EVENTS
            ),
            now,
        )

    def run(self, events: tuple[Event, ...], now: datetime) -> TimingBreakdown:
        return intervals(tuple(event for event in events if event.event_type in _RUN_EVENTS), now)

    def phase(self, events: tuple[Event, ...], phase_id: UUID, now: datetime) -> TimingBreakdown:
        return intervals(
            tuple(event for event in events if event.payload.phase_execution_id == phase_id), now
        )
