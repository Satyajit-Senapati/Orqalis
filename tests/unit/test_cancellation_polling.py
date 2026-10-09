"""Cancellation observation must not block or outlive its controller's lease."""

import asyncio
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Event, get_ident
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.domain.run import RunState
from orqalis.execution.cancellation import at_checkpoint, watch_cancellation
from orqalis.persistence.filesystem.locking import FileLock, LockTimeoutError


def factory_for(
    reader: Callable[..., Any], closed: Event | None = None
) -> Callable[[], ProjectUnitOfWork]:
    @contextmanager
    def factory() -> Iterator[Any]:
        try:
            yield SimpleNamespace(runs=SimpleNamespace(get=reader))
        finally:
            if closed is not None:
                closed.set()

    return cast(Callable[[], ProjectUnitOfWork], factory)


def test_contended_cancellation_poll_does_not_block_event_loop(tmp_path: Path) -> None:
    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        loop_thread = get_ident()
        poll_entered = asyncio.Event()
        release = Event()
        worker_closed = Event()
        reader_threads = []
        path = tmp_path / "run.state.lock"

        def work() -> str:
            try:
                with FileLock(path):
                    assert release.wait(3), "Event loop never released the worker"
                return "completed"
            finally:
                worker_closed.set()

        def read(_: Any) -> Any:
            reader_threads.append(get_ident())
            loop.call_soon_threadsafe(poll_entered.set)
            with FileLock(path, timeout=0.08):
                return SimpleNamespace(state=RunState.REVIEWING)

        async def release_from_loop() -> None:
            await poll_entered.wait()
            release.set()

        releaser = asyncio.create_task(release_from_loop())
        try:
            async with asyncio.timeout(5):
                result = await watch_cancellation(factory_for(read), uuid4(), at_checkpoint(work))
            assert result == "completed"
            assert worker_closed.is_set()
            assert reader_threads and all(thread != loop_thread for thread in reader_threads)
        finally:
            release.set()
            releaser.cancel()
            await asyncio.gather(releaser, return_exceptions=True)

    asyncio.run(scenario())


def test_transient_poll_lock_contention_does_not_abort_operation_or_lose_cancel() -> None:
    calls = 0
    operation_closed = Event()

    def read(_: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise LockTimeoutError("State writer is committing")
        return SimpleNamespace(state=RunState.CANCELLED)

    async def work() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            operation_closed.set()

    async def scenario() -> None:
        async with asyncio.timeout(3):
            with pytest.raises(asyncio.CancelledError):
                await watch_cancellation(factory_for(read), uuid4(), work())
        assert calls == 2 and operation_closed.is_set()

    asyncio.run(scenario())


def test_caller_cancel_drains_inflight_poll_and_operation_before_return() -> None:
    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        poll_entered = asyncio.Event()
        release = Event()
        poll_closed = Event()
        operation_closed = asyncio.Event()

        def read(_: Any) -> Any:
            loop.call_soon_threadsafe(poll_entered.set)
            assert release.wait(3), "Poll was abandoned during cancellation"
            return SimpleNamespace(state=RunState.REVIEWING)

        async def work() -> None:
            try:
                await asyncio.Event().wait()
            finally:
                operation_closed.set()

        watcher = asyncio.create_task(
            watch_cancellation(factory_for(read, poll_closed), uuid4(), work())
        )
        try:
            async with asyncio.timeout(5):
                await poll_entered.wait()
                watcher.cancel()
                async with asyncio.timeout(1):
                    await operation_closed.wait()
                assert not watcher.done()
                assert not poll_closed.is_set()
                watcher.cancel()
                await asyncio.sleep(0)
                assert not watcher.done()
                release.set()
                with pytest.raises(asyncio.CancelledError):
                    await watcher
            assert poll_closed.is_set() and operation_closed.is_set()
        finally:
            release.set()
            if not watcher.done():
                watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "error", [ValueError("Corrupt snapshot"), TimeoutError("Other storage timeout")]
)
def test_non_lock_read_errors_remain_visible_and_drain_operation(error: Exception) -> None:
    closed = Event()

    def read(_: Any) -> Any:
        raise error

    async def work() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            closed.set()

    async def scenario() -> None:
        with pytest.raises(type(error), match=str(error)):
            await watch_cancellation(factory_for(read), uuid4(), work())
        assert closed.is_set()

    asyncio.run(scenario())


def test_operation_lock_error_is_not_hidden_by_poll_contention() -> None:
    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        polled = asyncio.Event()

        def read(_: Any) -> Any:
            loop.call_soon_threadsafe(polled.set)
            raise LockTimeoutError("Cancellation observation was contended")

        async def work() -> None:
            await polled.wait()
            raise LockTimeoutError("Operation lock failure must remain visible")

        with pytest.raises(LockTimeoutError, match="Operation lock failure"):
            await watch_cancellation(factory_for(read), uuid4(), work())

    asyncio.run(scenario())
