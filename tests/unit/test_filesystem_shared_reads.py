from __future__ import annotations

import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from orqalis.persistence.filesystem import io
from orqalis.persistence.filesystem._windows_io import shared_read_opener


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native delete sharing")
def test_canonical_reader_retains_snapshot_while_writer_replaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "session.yaml"
    io.atomic_write_json(target, {"generation": 1})
    opened = threading.Event()
    release = threading.Event()
    original = io.shared_read_opener

    def paused_opener(path: str, flags: int) -> int:
        descriptor = original(path, flags)
        if Path(path) == target:
            opened.set()
            if not release.wait(5):
                os.close(descriptor)
                raise TimeoutError("Writer did not finish while snapshot reader was open")
        return descriptor

    monkeypatch.setattr(io, "shared_read_opener", paused_opener)
    with ThreadPoolExecutor(max_workers=1) as pool:
        reader = pool.submit(io.read_json_object, target)
        try:
            assert opened.wait(5), "Reader did not open the canonical snapshot"
            io.atomic_write_json(target, {"generation": 2})
        finally:
            release.set()
        assert reader.result(timeout=5) == {"generation": 1}
    assert io.read_json_object(target) == {"generation": 2}
    assert not list(tmp_path.glob(".session.yaml.*.tmp"))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native delete sharing")
def test_held_shared_reader_does_not_block_atomic_replacement(tmp_path: Path) -> None:
    target = tmp_path / "state.yaml"
    target.write_bytes(b"old")
    with open(target, "rb", opener=shared_read_opener) as reader:
        io.atomic_write_bytes(target, b"new")
        assert reader.read() == b"old"
        assert io.read_bytes(target) == b"new"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native sharing denial")
def test_uncooperative_external_reader_still_fails_without_mutating_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "state.yaml"
    target.write_bytes(b"old")
    with target.open("rb") as external_reader:
        with pytest.raises(PermissionError):
            io.atomic_write_bytes(target, b"new")
        assert external_reader.read() == b"old"
        assert io.read_bytes(target) == b"old"
    assert not list(tmp_path.glob(".state.yaml.*.tmp"))


def test_shared_snapshot_preserves_utf8_and_universal_newlines(tmp_path: Path) -> None:
    target = tmp_path / "memory.md"
    content = "café\r\nnext\rline\n".encode()
    target.write_bytes(content)
    assert io.read_bytes(target) == content
    assert io.read_text(target) == "café\nnext\nline\n"


def test_snapshot_missing_file_keeps_native_error_type_and_filename(tmp_path: Path) -> None:
    target = tmp_path / "missing.yaml"
    with pytest.raises(FileNotFoundError) as error:
        io.read_bytes(target)
    assert Path(str(error.value.filename)) == target


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native descriptor ownership")
def test_failed_descriptor_conversion_closes_owned_native_handle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if sys.platform == "win32":
        from orqalis.persistence.filesystem import _windows_io

        target = tmp_path / "state.yaml"
        target.write_bytes(b"old")
        closed: list[int] = []
        original_close = _windows_io._close_handle

        def fail_conversion(handle: int, flags: int) -> int:
            raise OSError("conversion failed")

        def record_close(handle: int) -> int:
            result = int(original_close(handle))
            closed.append(result)
            return result

        monkeypatch.setattr(_windows_io.msvcrt, "open_osfhandle", fail_conversion)
        monkeypatch.setattr(_windows_io, "_close_handle", record_close)
        with pytest.raises(OSError, match="conversion failed"):
            shared_read_opener(str(target), os.O_RDONLY)
        assert closed == [1]
        # A plain native reader succeeds immediately: conversion failed without
        # retaining an exclusive or leaked snapshot handle.
        assert target.read_bytes() == b"old"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native read-only opener")
@pytest.mark.parametrize("flag", [os.O_WRONLY, os.O_RDWR, os.O_CREAT, os.O_TRUNC, os.O_APPEND])
def test_snapshot_opener_rejects_write_flags_without_touching_file(
    tmp_path: Path, flag: int
) -> None:
    target = tmp_path / "state.yaml"
    target.write_bytes(b"old")
    with pytest.raises(ValueError, match="read-only"):
        shared_read_opener(str(target), flag)
    assert target.read_bytes() == b"old"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native atomic rename")
def test_native_rename_permission_denial_preserves_both_files_and_closes_handle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if sys.platform == "win32":
        import ctypes

        from orqalis.persistence.filesystem import _windows_io

        source, target = tmp_path / ".temporary", tmp_path / "state.yaml"
        source.write_bytes(b"new")
        target.write_bytes(b"old")
        closed: list[int] = []
        original_close = _windows_io._close_handle

        def denied(handle: int, kind: int, payload: object, size: int) -> int:
            ctypes.set_last_error(5)
            return 0

        def record_close(handle: int) -> int:
            result = int(original_close(handle))
            closed.append(result)
            return result

        monkeypatch.setattr(_windows_io, "_set_information", denied)
        monkeypatch.setattr(_windows_io, "_close_handle", record_close)
        with pytest.raises(PermissionError) as caught:
            _windows_io.replace_file(source, target)
        assert getattr(caught.value, "winerror", None) == 5
        assert closed == [1]
        assert source.read_bytes() == b"new" and target.read_bytes() == b"old"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native atomic rename")
def test_unsupported_native_rename_falls_back_once_after_closing_handle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if sys.platform == "win32":
        import ctypes

        from orqalis.persistence.filesystem import _windows_io

        source, target = tmp_path / ".temporary", tmp_path / "state.yaml"
        source.write_bytes(b"new")
        target.write_bytes(b"old")
        closed: list[int] = []
        fallback: list[tuple[Path, Path]] = []
        original_close, original_replace = _windows_io._close_handle, os.replace

        def unsupported(handle: int, kind: int, payload: object, size: int) -> int:
            ctypes.set_last_error(87)
            return 0

        def record_close(handle: int) -> int:
            result = int(original_close(handle))
            closed.append(result)
            return result

        def replace_once(old: Path, new: Path) -> None:
            assert closed == [1]
            fallback.append((old, new))
            original_replace(old, new)

        monkeypatch.setattr(_windows_io, "_set_information", unsupported)
        monkeypatch.setattr(_windows_io, "_close_handle", record_close)
        monkeypatch.setattr(os, "replace", replace_once)
        _windows_io.replace_file(source, target)
        assert fallback == [(source, target)]
        assert target.read_bytes() == b"new" and not source.exists()
