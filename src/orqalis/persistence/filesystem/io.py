"""Validated, interruption-safe primitives for filesystem persistence."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import time
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import BinaryIO

from orqalis.domain.errors import PolicyDeniedError
from orqalis.persistence.filesystem._windows_io import replace_file
from orqalis.persistence.filesystem._windows_io import shared_read_opener as shared_read_opener
from orqalis.persistence.filesystem.locking import FileLock

_replace_file = replace_file


class FilesystemFormatError(ValueError):
    """Raised when a canonical JSON or JSONL document is malformed."""


def ensure_no_filesystem_links(path: Path) -> Path:
    """Reject symlink/junction traversal for canonical project-store paths."""

    candidate = path.expanduser().absolute()
    for component in (candidate, *candidate.parents):
        try:
            metadata = component.lstat()
        except (FileNotFoundError, NotADirectoryError):
            continue
        # One metadata snapshot checks both link forms without following this entry.
        junction_tag = getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_reparse_tag", 0) == junction_tag:
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


def _read_bytes(target: Path) -> bytes:
    with (
        target.open("rb")
        if os.name != "nt"
        else open(target, "rb", opener=shared_read_opener) as stream
    ):
        return stream.read()


def read_bytes(path: Path) -> bytes:
    """Read a guarded immutable snapshot without blocking Windows replacement."""

    return _read_bytes(ensure_no_filesystem_links(path))


def read_text(path: Path) -> str:
    """Read guarded UTF-8 text with the usual universal-newline behavior."""

    target = ensure_no_filesystem_links(path)
    with open(
        target, encoding="utf-8", opener=shared_read_opener if os.name == "nt" else None
    ) as stream:
        return stream.read()


class _TemporaryIdentityError(OSError):
    """The temporary pathname no longer identifies our owned regular file."""


def _require_temporary_identity(temporary: Path, identity: os.stat_result, content: bytes) -> None:
    ensure_no_filesystem_links(temporary.parent)
    current = os.stat(temporary, follow_symlinks=False)
    if not stat.S_ISREG(current.st_mode) or getattr(current, "st_file_attributes", 0) & 0x400:
        raise _TemporaryIdentityError("Temporary file is not an owned regular file")
    if identity.st_ino:
        if not os.path.samestat(identity, current):
            raise _TemporaryIdentityError("Temporary file identity changed")
    elif _read_bytes(temporary) != content:
        # Filesystems without stable inode identities retain pathname verification.
        raise OSError("Temporary file validation failed")


def _verify_temporary(temporary: Path, stream: BinaryIO, content: bytes) -> os.stat_result:
    stream.seek(0)
    if stream.read() != content:
        raise OSError("Temporary file validation failed")
    return os.fstat(stream.fileno())


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
    identity_lost = False
    try:
        with os.fdopen(descriptor, "w+b") as stream:
            _write_all(stream, content)
            stream.flush()
            os.fsync(stream.fileno())
            identity = _verify_temporary(temporary, stream, content)
            identity_lost = True
            _require_temporary_identity(temporary, identity, content)
            identity_lost = False
        identity_lost = True
        _require_temporary_identity(temporary, identity, content)
        identity_lost = False
        os.chmod(temporary, mode if mode is not None else existing_mode or 0o644)
        # Transient Windows sharing denials get at most 300 ms of backoff.
        for attempt in range(5):
            try:
                identity_lost = True
                _require_temporary_identity(temporary, identity, content)
                identity_lost = False
                _replace_file(temporary, target)
                break
            except PermissionError as exc:
                if (
                    os.name != "nt"
                    or getattr(exc, "winerror", None) not in {5, 32, 33}
                    or attempt == 4
                ):
                    raise
                ensure_no_filesystem_links(target)
                time.sleep(0.02 * (2**attempt))
                ensure_no_filesystem_links(target)
        _fsync_directory(target.parent)
    finally:
        if not identity_lost:
            with suppress(FileNotFoundError):
                try:
                    temporary.unlink()
                except PermissionError as exc:
                    if os.name != "nt" or getattr(exc, "winerror", None) != 5:
                        raise
                    ensure_no_filesystem_links(temporary)
                    metadata = temporary.lstat()
                    readonly_flag = getattr(stat, "FILE_ATTRIBUTE_READONLY", 0x1)
                    if not stat.S_ISREG(metadata.st_mode) or not (
                        getattr(metadata, "st_file_attributes", 0) & readonly_flag
                    ):
                        raise
                    # Only clear READONLY on this failed write's owned temporary.
                    os.chmod(temporary, stat.S_IMODE(metadata.st_mode) | stat.S_IWRITE)
                    ensure_no_filesystem_links(temporary)
                    temporary.unlink()


def atomic_write_json(path: Path, value: object) -> None:
    """Write canonical JSON atomically.

    Orqalis uses this serialization for structured ``.yaml`` files as well: JSON
    is a strict subset of YAML 1.2 and remains readable by JSON and YAML tooling.
    """

    atomic_write_bytes(path, _encoded_json(value))


def read_json(path: Path) -> object:
    target = ensure_no_filesystem_links(path)
    return _decode_json(_read_bytes(target), target)


def read_json_object(path: Path) -> dict[str, object]:
    value = read_json(path)
    if not isinstance(value, dict):
        raise FilesystemFormatError(f"Expected a JSON object: {path}")
    return value


def read_json_object_with_sha256(path: Path) -> tuple[dict[str, object], str]:
    """Strictly decode and hash the same single read of a JSON object."""

    target = ensure_no_filesystem_links(path)
    content = _read_bytes(target)
    value = _decode_json(content, target)
    if not isinstance(value, dict):
        raise FilesystemFormatError(f"Expected JSON object: {target}")
    return value, hashlib.sha256(content).hexdigest()


def _jsonl_lock(path: Path) -> Path:
    return path.with_name(f".{path.name}.lock")


def read_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    target = ensure_no_filesystem_links(path)
    with FileLock(_jsonl_lock(target)):
        if not target.exists():
            return ()
        content = _read_bytes(target)
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
        lines = _read_bytes(target).splitlines(keepends=True)
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
