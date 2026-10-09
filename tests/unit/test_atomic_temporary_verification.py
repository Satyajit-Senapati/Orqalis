from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO

import pytest

from orqalis.persistence.filesystem import io


@pytest.mark.parametrize("written", [b"wrong", b"af"])
def test_corrupt_temporary_never_replaces_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, written: bytes
) -> None:
    target = tmp_path / "state.bin"
    target.write_bytes(b"before")
    replacements: list[Path] = []

    def corrupt(stream: BinaryIO, content: bytes) -> None:
        stream.write(written)

    monkeypatch.setattr(io, "_write_all", corrupt)
    monkeypatch.setattr(io, "_replace_file", lambda source, target: replacements.append(source))
    with pytest.raises(OSError, match="Temporary file validation failed"):
        io.atomic_write_bytes(target, b"after")
    assert target.read_bytes() == b"before"
    assert replacements == []
    assert not list(tmp_path.glob(".state.bin.*.tmp"))


@pytest.mark.parametrize("progress", [0, 3])
def test_real_short_writes_complete_or_fail_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, progress: int
) -> None:
    target = tmp_path / "state.bin"
    target.write_bytes(b"before")
    write_all = io._write_all
    payload = bytes(range(256)) * 20

    class ShortWriter:
        def __init__(self, stream: BinaryIO) -> None:
            self.stream = stream

        def write(self, content: memoryview) -> int:
            return self.stream.write(content[:progress]) if progress else 0

    def short_write(stream: BinaryIO, content: bytes) -> None:
        write_all(ShortWriter(stream), content)  # type: ignore[arg-type]

    monkeypatch.setattr(io, "_write_all", short_write)
    if progress:
        io.atomic_write_bytes(target, payload)
        assert target.read_bytes() == payload
    else:
        with pytest.raises(OSError, match="did not make progress"):
            io.atomic_write_bytes(target, payload)
        assert target.read_bytes() == b"before"
    assert not list(tmp_path.glob(".state.bin.*.tmp"))


def test_same_content_temporary_substitution_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state.bin"
    target.write_bytes(b"before")
    chmod = os.chmod
    replacements: list[Path] = []

    def substitute(path: Path, mode: int) -> None:
        chmod(path, mode)
        if path.name.startswith(".state.bin."):
            replacement = tmp_path / "substitute.bin"
            replacement.write_bytes(b"after")
            os.replace(replacement, path)

    monkeypatch.setattr(os, "chmod", substitute)
    monkeypatch.setattr(io, "_replace_file", lambda source, target: replacements.append(source))
    with pytest.raises(OSError, match="Temporary file identity changed"):
        io.atomic_write_bytes(target, b"after")
    assert target.read_bytes() == b"before"
    assert replacements == []
    foreign = list(tmp_path.glob(".state.bin.*.tmp"))
    assert len(foreign) == 1
    assert foreign[0].read_bytes() == b"after"
    foreign[0].unlink()  # The test owns this substituted file; product cleanup does not.


@pytest.mark.parametrize(
    "failure", [PermissionError("metadata denied"), OSError("metadata failed")]
)
def test_unverified_parent_guard_preserves_primary_without_cleanup_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: OSError
) -> None:
    target = tmp_path / "state.bin"
    target.write_bytes(b"before")
    guard = io.ensure_no_filesystem_links
    unlink = Path.unlink
    unlinks: list[Path] = []

    def fail_parent(path: Path) -> Path:
        if path == tmp_path:
            raise failure
        return guard(path)

    def tracked_unlink(path: Path, *args: object, **kwargs: object) -> None:
        unlinks.append(path)
        unlink(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(io, "ensure_no_filesystem_links", fail_parent)
    monkeypatch.setattr(Path, "unlink", tracked_unlink)
    with pytest.raises(OSError) as caught:
        io.atomic_write_bytes(target, b"after")
    assert caught.value is failure
    assert target.read_bytes() == b"before"
    assert unlinks == []
    temporary = list(tmp_path.glob(".state.bin.*.tmp"))
    assert len(temporary) == 1
    assert temporary[0].read_bytes() == b"after"
    unlink(temporary[0])  # Owned test cleanup after the asserted product refusal.
