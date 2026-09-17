"""Small cross-platform advisory file locks for the project-local store."""

from __future__ import annotations

import errno
import importlib
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import BinaryIO, Protocol, cast


class LockTimeoutError(TimeoutError):
    """Raised when an advisory filesystem lock cannot be acquired in time."""


@dataclass(slots=True)
class _LockState:
    gate: threading.RLock = field(default_factory=threading.RLock)
    handle: BinaryIO | None = None
    depth: int = 0


_REGISTRY_GUARD = threading.Lock()
_REGISTRY: dict[str, _LockState] = {}


class _FcntlModule(Protocol):
    LOCK_EX: int
    LOCK_NB: int
    LOCK_UN: int

    def flock(self, descriptor: int, operation: int) -> object: ...


def _state_for(path: Path) -> _LockState:
    key = os.path.normcase(str(path.absolute()))
    with _REGISTRY_GUARD:
        return _REGISTRY.setdefault(key, _LockState())


def _try_platform_lock(handle: BinaryIO) -> bool:
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl = cast(_FcntlModule, importlib.import_module("fcntl"))
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if isinstance(exc, BlockingIOError) or exc.errno in {errno.EACCES, errno.EAGAIN}:
            return False
        raise
    return True


def _platform_unlock(handle: BinaryIO) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl = cast(_FcntlModule, importlib.import_module("fcntl"))
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class FileLock:
    """An exclusive advisory lock that is reentrant per path and thread.

    Lock files are intentionally retained after release. Removing an advisory lock
    file creates an inode race in which two processes can each believe they hold the
    same logical lock.
    """

    def __init__(
        self,
        path: Path,
        timeout: float = 10.0,
        poll_interval: float = 0.05,
    ) -> None:
        if timeout < 0:
            raise ValueError("Lock timeout must be non-negative")
        if poll_interval <= 0:
            raise ValueError("Lock poll interval must be positive")
        self.path = path.expanduser().absolute()
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._state = _state_for(self.path)
        self._acquisitions = 0

    def acquire(self) -> None:
        deadline = time.monotonic() + self.timeout
        if not self._state.gate.acquire(timeout=self.timeout):
            raise LockTimeoutError(f"Timed out acquiring lock: {self.path}")
        try:
            if self._state.depth:
                self._state.depth += 1
                self._acquisitions += 1
                return

            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = self.path.open("a+b")
            try:
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                    os.fsync(handle.fileno())
                while not _try_platform_lock(handle):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise LockTimeoutError(f"Timed out acquiring lock: {self.path}")
                    time.sleep(min(self.poll_interval, remaining))
            except BaseException:
                handle.close()
                raise
            self._state.handle = handle
            self._state.depth = 1
            self._acquisitions = 1
        except BaseException:
            self._state.gate.release()
            raise

    def release(self) -> None:
        if self._acquisitions <= 0 or self._state.depth <= 0:
            raise RuntimeError("Cannot release a lock that is not held by this instance")
        self._acquisitions -= 1
        self._state.depth -= 1
        try:
            if self._state.depth == 0:
                handle = self._state.handle
                self._state.handle = None
                if handle is None:
                    raise RuntimeError("Filesystem lock state is inconsistent")
                try:
                    _platform_unlock(handle)
                finally:
                    handle.close()
        finally:
            self._state.gate.release()

    def __enter__(self) -> FileLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()
