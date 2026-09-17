import asyncio
import threading
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from orqalis.domain.events import Event, EventType
from orqalis.observability.event_bus import ProjectEventBus


def event(run_id, sequence: int) -> Event:  # type: ignore[no-untyped-def]
    return Event(
        project_id=uuid4(),
        run_id=run_id,
        sequence=sequence,
        event_type=EventType.RUN_STARTED,
        occurred_at=datetime.now(UTC),
        idempotency_key=f"event-{sequence}",
    )


def test_bus_filters_runs_and_unsubscribes() -> None:
    async def exercise() -> None:
        bus = ProjectEventBus()
        run_id, other_id = uuid4(), uuid4()

        async with bus.subscribe(run_id) as subscription:
            assert bus.subscriber_count(run_id) == 1
            bus.publish((event(other_id, 1), event(run_id, 2)))
            notification = await subscription.receive(timeout=1)
            assert (notification.run_id, notification.sequence) == (run_id, 2)

        assert bus.subscriber_count() == 0

    asyncio.run(exercise())


def test_bus_is_safe_to_publish_from_worker_thread() -> None:
    async def exercise() -> None:
        bus = ProjectEventBus()
        run_id = uuid4()

        async with bus.subscribe(run_id) as subscription:
            worker = threading.Thread(target=bus.publish, args=((event(run_id, 1),),))
            worker.start()
            worker.join(timeout=1)
            assert not worker.is_alive()
            assert (await subscription.receive(timeout=1)).sequence == 1

    asyncio.run(exercise())


def test_bounded_queue_keeps_latest_durable_cursor() -> None:
    async def exercise() -> None:
        bus = ProjectEventBus(queue_size=1)
        run_id = uuid4()

        async with bus.subscribe(run_id) as subscription:
            bus.publish(event(run_id, sequence) for sequence in range(1, 6))
            await asyncio.sleep(0)
            assert (await subscription.receive(timeout=1)).sequence == 5

    asyncio.run(exercise())


def test_bus_rejects_invalid_queue_size() -> None:
    with pytest.raises(ValueError, match="positive"):
        ProjectEventBus(queue_size=0)
