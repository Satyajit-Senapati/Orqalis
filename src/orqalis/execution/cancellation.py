import asyncio
from collections.abc import Callable, Coroutine
from contextvars import ContextVar
from threading import Event
from typing import Any
from uuid import UUID

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.domain.run import RunState
from orqalis.persistence.filesystem.locking import LockTimeoutError

_cancel: ContextVar[Event | None] = ContextVar("orqalis_command_cancel", default=None)


def cancellation_requested() -> bool:
    signal = _cancel.get()
    return signal is not None and signal.is_set()


async def at_checkpoint[T](function: Callable[..., T], *args: Any) -> T:
    """Retain the run lease until an owned thread acknowledges cancellation."""
    signal = Event()

    def execute() -> T:
        token = _cancel.set(signal)
        try:
            return function(*args)
        finally:
            _cancel.reset(token)

    task = asyncio.create_task(asyncio.to_thread(execute))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        signal.set()
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        # Retrieve an error so cancelled callers do not leak background exceptions.
        if not task.cancelled():
            task.exception()
        raise


def _persisted_cancel_requested(factory: Callable[[], ProjectUnitOfWork], run_id: UUID) -> bool:
    with factory() as uow:
        run = uow.runs.get(run_id)
    return run is not None and run.state == RunState.CANCELLED


async def _poll_cancellation(
    factory: Callable[[], ProjectUnitOfWork], run_id: UUID, operation: asyncio.Task[Any]
) -> bool:
    poll = asyncio.create_task(at_checkpoint(_persisted_cancel_requested, factory, run_id))
    try:
        return await asyncio.shield(poll)
    except asyncio.CancelledError:
        # Notify actual work before waiting for a contended read to close. Both
        # tasks remain owned: the caller's finally drains the operation as well.
        operation.cancel()
        poll.cancel()
        while not poll.done():
            try:
                await asyncio.shield(poll)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not poll.cancelled():
            poll.exception()
        raise


async def watch_cancellation[T](
    factory: Callable[[], ProjectUnitOfWork],
    run_id: UUID,
    operation: Coroutine[Any, Any, T],
) -> T:
    task = asyncio.create_task(operation)
    try:
        while not task.done():
            await asyncio.wait({task}, timeout=0.25)
            if not task.done():
                try:
                    # A state writer may hold the file lock. Never wait for it on
                    # the event loop, and retain ownership until the read closes.
                    cancelled = await _poll_cancellation(factory, run_id, task)
                except LockTimeoutError:
                    # Contention makes this observation unavailable; it does not
                    # invalidate the operation or establish a cancellation state.
                    continue
                if cancelled:
                    task.cancel()
                    break
        return await task
    finally:
        if not task.done():
            task.cancel()
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
