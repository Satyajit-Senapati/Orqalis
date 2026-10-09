from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import BinaryIO

import pytest

from orqalis.persistence.filesystem import locking
from orqalis.persistence.filesystem.locking import FileLock, LockTimeoutError


@pytest.mark.parametrize("depth", [1, 2])
def test_wrong_thread_release_preserves_owner_and_native_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, depth: int
) -> None:
    lock = FileLock(tmp_path / "lease.lock")
    for _ in range(depth):
        lock.acquire()
    handle = lock._state.handle
    assert handle is not None
    unlocks: list[BinaryIO] = []
    original_unlock = locking._platform_unlock

    def observed_unlock(stream: BinaryIO) -> None:
        unlocks.append(stream)
        original_unlock(stream)

    monkeypatch.setattr(locking, "_platform_unlock", observed_unlock)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(RuntimeError, match="unowned"):
            pool.submit(lock.release).result(timeout=1)
        assert lock._acquisitions == lock._state.depth == depth
        assert lock._state.handle is handle and not handle.closed
        assert unlocks == []
        with pytest.raises(LockTimeoutError):
            pool.submit(FileLock(lock.path, timeout=0).acquire).result(timeout=1)
        for remaining in range(depth - 1, -1, -1):
            lock.release()
            assert lock._acquisitions == lock._state.depth == remaining
        assert handle.closed and lock._state.handle is None and unlocks == [handle]

        def successor() -> None:
            with FileLock(lock.path, timeout=1):
                assert lock._state.depth == 1

        pool.submit(successor).result(timeout=2)
    assert lock._state.depth == 0 and lock._state.handle is None
    assert len(unlocks) == 2 and unlocks[1] is not handle
