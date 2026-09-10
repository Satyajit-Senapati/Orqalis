import asyncio
from collections.abc import Callable, Coroutine
from contextvars import ContextVar
from threading import Event
from typing import Any
from uuid import UUID

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.domain.run import RunState

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
                with factory() as uow:
                    run = uow.runs.get(run_id)
                if run and run.state == RunState.CANCELLED:
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
