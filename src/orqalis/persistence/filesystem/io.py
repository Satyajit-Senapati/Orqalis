"""Validated, interruption-safe primitives for filesystem persistence."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import BinaryIO

from orqalis.domain.errors import PolicyDeniedError
from orqalis.persistence.filesystem.locking import FileLock


class FilesystemFormatError(ValueError):
    """Raised when a canonical JSON or JSONL document is malformed."""


def ensure_no_filesystem_links(path: Path) -> Path:
    """Reject symlink/junction traversal for canonical project-store paths."""

    candidate = path.expanduser().absolute()
    for component in (candidate, *candidate.parents):
        is_junction = getattr(component, "is_junction", lambda: False)
        if component.is_symlink() or is_junction():
            raise PolicyDeniedError(
                f"Project storage path traverses a link or junction: {component}"
            )
    return candidate


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise FilesystemFormatError(f"Duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise FilesystemFormatError(f"Non-finite JSON number is not supported: {value}")


def _decode_json(content: bytes, path: Path) -> object:
    try:
        text = content.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, FilesystemFormatError) as exc:
        if isinstance(exc, FilesystemFormatError):
            raise
        raise FilesystemFormatError(f"Invalid JSON document: {path}") from exc


def _encoded_json(value: object) -> bytes:
    try:
        encoded = (
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise FilesystemFormatError("Value is not valid JSON") from exc
    _decode_json(encoded, Path("<memory>"))
    return encoded


def _encoded_json_line(value: object) -> bytes:
    try:
        encoded = (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise FilesystemFormatError("Value is not valid JSON") from exc
    _decode_json(encoded, Path("<memory>"))
    return encoded


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_all(stream: BinaryIO, content: bytes) -> None:
    view = memoryview(content)
    while view:
        written = stream.write(view)
        if written is None or written <= 0:
            raise OSError("Temporary file write did not make progress")
        view = view[written:]


def atomic_write_bytes(path: Path, content: bytes, *, mode: int | None = None) -> None:
    """Replace ``path`` only after a complete, flushed, verified temporary write."""

    if not isinstance(content, bytes):
        raise TypeError("Atomic writes require bytes")
    target = ensure_no_filesystem_links(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    existing_mode = None
    with suppress(FileNotFoundError):
        existing_mode = stat.S_IMODE(target.stat().st_mode)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            _write_all(stream, content)
            stream.flush()
            os.fsync(stream.fileno())
        if temporary.read_bytes() != content:
            raise OSError("Temporary file validation failed")
        os.chmod(temporary, mode if mode is not None else existing_mode or 0o644)
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    finally:
        with suppress(FileNotFoundError):
            temporary.unlink()


def atomic_write_json(path: Path, value: object) -> None:
    """Write canonical JSON atomically.

    Orqalis uses this serialization for structured ``.yaml`` files as well: JSON
    is a strict subset of YAML 1.2 and remains readable by JSON and YAML tooling.
    """

    atomic_write_bytes(path, _encoded_json(value))


def read_json(path: Path) -> object:
    target = ensure_no_filesystem_links(path)
    return _decode_json(target.read_bytes(), target)


def read_json_object(path: Path) -> dict[str, object]:
    value = read_json(path)
    if not isinstance(value, dict):
        raise FilesystemFormatError(f"Expected a JSON object: {path}")
    return value


def _jsonl_lock(path: Path) -> Path:
    return path.with_name(f".{path.name}.lock")


def read_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    target = ensure_no_filesystem_links(path)
    with FileLock(_jsonl_lock(target)):
        if not target.exists():
            return ()
        content = target.read_bytes()
    if not content:
        return ()
    if not content.endswith(b"\n"):
        raise FilesystemFormatError(f"JSONL file ends with an incomplete record: {target}")
    records: list[dict[str, object]] = []
    for number, line in enumerate(content.splitlines(), start=1):
        if not line:
            raise FilesystemFormatError(f"Blank JSONL record at line {number}: {target}")
        value = _decode_json(line, target)
        if not isinstance(value, dict):
            raise FilesystemFormatError(f"Expected JSON object at line {number}: {target}")
        records.append(value)
    return tuple(records)


def repair_jsonl_prefix(path: Path, record_count: int) -> tuple[dict[str, object], ...]:
    """Atomically retain a validated committed prefix after an interrupted append."""

    if isinstance(record_count, bool) or record_count < 0:
        raise ValueError("JSONL prefix length must be a non-negative integer")
    target = ensure_no_filesystem_links(path)
    with FileLock(_jsonl_lock(target)):
        if not target.exists():
            if record_count:
                raise FilesystemFormatError(
                    f"JSONL file has fewer than {record_count} committed records: {target}"
                )
            return ()
        lines = target.read_bytes().splitlines(keepends=True)
        prefix_lines = lines[:record_count]
        if len(prefix_lines) != record_count or any(
            not line.endswith(b"\n") for line in prefix_lines
        ):
            raise FilesystemFormatError(f"JSONL file has an incomplete committed prefix: {target}")
        records: list[dict[str, object]] = []
        for number, line in enumerate(prefix_lines, start=1):
            value = _decode_json(line, target)
            if not isinstance(value, dict):
                raise FilesystemFormatError(f"Expected JSON object at line {number}: {target}")
            records.append(value)
        atomic_write_bytes(target, b"".join(prefix_lines))
        return tuple(records)


def append_jsonl_atomic(
    path: Path,
    record: Mapping[str, object],
    *,
    lock_timeout: float = 10.0,
) -> None:
    """Append one complete JSON object under an inter-process advisory lock."""

    if not isinstance(record, Mapping):
        raise FilesystemFormatError("JSONL records must be objects")
    encoded = _encoded_json_line(dict(record))
    target = ensure_no_filesystem_links(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(_jsonl_lock(target), timeout=lock_timeout):
        if target.is_symlink():
            raise OSError(f"Refusing to append through a symbolic link: {target}")
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        flags |= getattr(os, "O_BINARY", 0)
        descriptor = os.open(target, flags, 0o644)
        original_size = os.lseek(descriptor, 0, os.SEEK_END)
        try:
            remaining = memoryview(encoded)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise OSError("Atomic JSONL append was incomplete")
                remaining = remaining[written:]
            os.fsync(descriptor)
        except BaseException:
            os.ftruncate(descriptor, original_size)
            os.fsync(descriptor)
            raise
        finally:
            os.close(descriptor)
