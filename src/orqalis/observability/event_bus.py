"""Process-local notification bus for events already committed to a project store.

The durable event stream remains authoritative.  This bus only wakes live consumers;
subscribers must use event sequence numbers to retrieve any gap from the EventStore.
That makes bounded queues safe and keeps reconnect/restart semantics filesystem-backed.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID

from orqalis.domain.events import Event


@dataclass(frozen=True, slots=True)
class EventNotification:
    """A committed-event notification carrying the durable stream cursor."""

    run_id: UUID
    sequence: int


@dataclass(eq=False, slots=True)
class _Subscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[EventNotification]


class EventSubscription:
    """One run-filtered asynchronous subscription."""

    def __init__(self, subscriber: _Subscriber) -> None:
        self._subscriber = subscriber

    async def receive(self, timeout: float | None = None) -> EventNotification:
        """Wait for the latest available commit notification."""

        if timeout is None:
            return await self._subscriber.queue.get()
        return await asyncio.wait_for(self._subscriber.queue.get(), timeout)


class ProjectEventBus:
    """Thread-safe fan-out for committed events in one Orqalis process.

    Synchronous orchestration commonly commits from a worker thread while WebSocket
    subscribers live on an asyncio loop.  ``call_soon_threadsafe`` bridges those two
    worlds.  A full queue drops older notifications and retains the newest cursor;
    consumers then fill the sequence gap from the canonical JSONL event stream.
    """

    def __init__(self, queue_size: int = 256) -> None:
        if queue_size < 1:
            raise ValueError("Event notification queue size must be positive")
        self._queue_size = queue_size
        self._lock = threading.Lock()
        self._subscribers: dict[UUID, set[_Subscriber]] = {}

    @asynccontextmanager
    async def subscribe(self, run_id: UUID) -> AsyncIterator[EventSubscription]:
        """Register before replaying durable events to avoid a replay/live race."""

        subscriber = _Subscriber(
            loop=asyncio.get_running_loop(),
            queue=asyncio.Queue(maxsize=self._queue_size),
        )
        with self._lock:
            self._subscribers.setdefault(run_id, set()).add(subscriber)
        try:
            yield EventSubscription(subscriber)
        finally:
            with self._lock:
                subscribers = self._subscribers.get(run_id)
                if subscribers is not None:
                    subscribers.discard(subscriber)
                    if not subscribers:
                        self._subscribers.pop(run_id, None)

    def publish(self, events: Iterable[Event]) -> None:
        """Notify subscribers after the supplied events have become durable."""

        for event in events:
            notification = EventNotification(run_id=event.run_id, sequence=event.sequence)
            with self._lock:
                subscribers = tuple(self._subscribers.get(event.run_id, ()))
            for subscriber in subscribers:
                try:
                    subscriber.loop.call_soon_threadsafe(
                        self._offer_latest, subscriber.queue, notification
                    )
                except RuntimeError:
                    # A loop can close between copying the subscriber set and dispatch.
                    continue

    def subscriber_count(self, run_id: UUID | None = None) -> int:
        """Return diagnostic subscriber counts without exposing mutable internals."""

        with self._lock:
            if run_id is not None:
                return len(self._subscribers.get(run_id, ()))
            return sum(len(subscribers) for subscribers in self._subscribers.values())

    @staticmethod
    def _offer_latest(
        queue: asyncio.Queue[EventNotification], notification: EventNotification
    ) -> None:
        while queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        queue.put_nowait(notification)


__all__ = ["EventNotification", "EventSubscription", "ProjectEventBus"]
