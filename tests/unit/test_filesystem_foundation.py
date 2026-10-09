from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from orqalis.domain.errors import PolicyDeniedError
from orqalis.persistence.filesystem import (
    DEFAULT_STORE_GITIGNORE,
    FileLock,
    FilesystemFormatError,
    LockTimeoutError,
    ManifestNotFoundError,
    ManifestValidationError,
    ProjectLayout,
    ProjectRootError,
    SchemaMigrationRequired,
    UnsupportedSchemaError,
    append_jsonl_atomic,
    atomic_write_bytes,
    atomic_write_json,
    bootstrap_project_store,
    load_manifest,
    migrate_manifest,
    read_json_object,
    read_jsonl,
    resolve_project_root,
)
from orqalis.persistence.filesystem.io import (
    ensure_no_filesystem_links,
    read_json_object_with_sha256,
)
from orqalis.persistence.filesystem.locking import _ReentrantGate
from tests.conftest import fixture_git


def test_resolve_root_prefers_explicit_then_git_then_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ORQALIS_PROJECT_ROOT", raising=False)
    repository = tmp_path / "repo"
    repository.mkdir()
    fixture_git(repository, "init", "-b", "main")
    nested = repository / "src" / "feature"
    nested.mkdir(parents=True)
    explicit = tmp_path / "explicit"
    explicit.mkdir()

    assert resolve_project_root(explicit, cwd=nested) == explicit.resolve()
    assert resolve_project_root(nested, cwd=explicit) == repository.resolve()
    assert resolve_project_root(cwd=nested) == repository.resolve()
    assert resolve_project_root(cwd=explicit) == explicit.resolve()


def test_invalid_explicit_root_never_falls_back_to_other_repository(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    fixture_git(repository, "init", "-b", "main")
    with pytest.raises(ProjectRootError):
        resolve_project_root(tmp_path / "missing", cwd=repository)


def test_configured_root_is_authoritative_and_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    fixture_git(repository, "init", "-b", "main")
    configured = tmp_path / "configured"
    configured.mkdir()
    monkeypatch.setenv("ORQALIS_PROJECT_ROOT", str(configured))
    assert resolve_project_root(cwd=repository) == configured.resolve()
    nested = repository / "src" / "feature"
    nested.mkdir(parents=True)
    monkeypatch.setenv("ORQALIS_PROJECT_ROOT", str(nested))
    assert resolve_project_root(cwd=configured) == repository.resolve()
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    assert resolve_project_root(explicit, cwd=repository) == explicit.resolve()
    monkeypatch.setenv("ORQALIS_PROJECT_ROOT", str(tmp_path / "missing"))
    with pytest.raises(ProjectRootError):
        resolve_project_root(cwd=repository)


def test_layout_rejects_path_and_identifier_escape(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)
    assert layout.task("ORQ-20260916-0001") == layout.tasks / "ORQ-20260916-0001"
    assert layout.lock("memory") == layout.locks / "memory.lock"
    with pytest.raises(PolicyDeniedError):
        layout.task("../outside")
    with pytest.raises(PolicyDeniedError):
        layout.contained(tmp_path / "outside")


def test_bootstrap_writes_schema_v2_json_as_yaml_and_selective_policy(
    git_repo: Path,
) -> None:
    initialized = datetime(2026, 9, 16, 8, 50, tzinfo=UTC)
    layout = bootstrap_project_store(git_repo, initialized_at=initialized)
    manifest = load_manifest(layout)
    config = read_json_object(layout.config)

    assert manifest["schema_version"] == 2
    assert manifest["storage"] == {"backend": "filesystem"}
    assert manifest["initialized_at"] == initialized.isoformat()
    UUID(manifest["project"]["id"])  # type: ignore[index]
    assert manifest["project"]["name"] == git_repo.name  # type: ignore[index]
    assert manifest["graph"]["indexed_branch"] == "main"  # type: ignore[index]
    assert manifest["graph"]["indexed_commit"] == fixture_git(  # type: ignore[index]
        git_repo, "rev-parse", "HEAD"
    )
    assert config["memory"] == {"durable_updates": "review"}
    assert json.loads(layout.manifest.read_text(encoding="utf-8")) == manifest
    assert layout.gitignore.read_text(encoding="utf-8") == DEFAULT_STORE_GITIGNORE
    assert "/cache/" in DEFAULT_STORE_GITIGNORE
    assert "/runtime/" in DEFAULT_STORE_GITIGNORE
    assert "/memory/" not in DEFAULT_STORE_GITIGNORE.splitlines()
    assert "/tasks/" not in DEFAULT_STORE_GITIGNORE.splitlines()
    assert not layout.project.exists()
    assert bootstrap_project_store(git_repo) == layout


def test_bootstrap_does_not_borrow_parent_git_identity(tmp_path: Path) -> None:
    repository = tmp_path / "outer"
    repository.mkdir()
    fixture_git(repository, "init", "-b", "main")
    nested_project = repository / "nested-project"
    nested_project.mkdir()

    layout = bootstrap_project_store(nested_project)
    graph = load_manifest(layout)["graph"]
    assert graph == {"schema_version": 1, "indexed_branch": None, "indexed_commit": None}


def test_bootstrap_regenerates_gitignore_from_tracking_policy(git_repo: Path) -> None:
    layout = bootstrap_project_store(git_repo)
    config = read_json_object(layout.config)
    config["git"] = {
        "track_execution_events": True,
        "track_generated_graph_html": True,
        "track_project_memory": False,
        "track_task_history": False,
    }
    atomic_write_json(layout.config, config)

    bootstrap_project_store(git_repo)

    patterns = layout.gitignore.read_text(encoding="utf-8").splitlines()
    assert "/cache/" in patterns
    assert "/runtime/" in patterns
    assert "/memory/" in patterns
    assert "/tasks/" in patterns
    assert "/memory/graph/graph.html" not in patterns
    assert "/tasks/*/execution/events.jsonl" not in patterns


def test_bootstrap_rejects_invalid_tracking_policy(git_repo: Path) -> None:
    layout = bootstrap_project_store(git_repo)
    config = read_json_object(layout.config)
    config["git"] = {"track_task_history": "sometimes"}
    atomic_write_json(layout.config, config)

    with pytest.raises(ManifestValidationError, match="track_task_history"):
        bootstrap_project_store(git_repo)


def test_atomic_json_write_preserves_original_and_cleans_temp_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state.json"
    atomic_write_json(target, {"state": "before"})

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated interruption")

    monkeypatch.setattr("orqalis.persistence.filesystem.io._replace_file", fail_replace)
    with pytest.raises(OSError, match="simulated interruption"):
        atomic_write_json(target, {"state": "after"})
    assert read_json_object(target) == {"state": "before"}
    assert list(tmp_path.glob(".state.json.*.tmp")) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing-denial behavior")
@pytest.mark.parametrize("denials", [1, 2, 3, 4])
def test_atomic_write_recovers_from_bounded_windows_sharing_denials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, denials: int
) -> None:
    target = tmp_path / "state.json"
    target.write_bytes(b"before")
    from orqalis.persistence.filesystem import io

    replace = io._replace_file
    calls = 0

    def temporarily_denied(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls <= denials:
            raise PermissionError(13, "sharing denied", str(destination), 32)
        replace(source, destination)

    monkeypatch.setattr("orqalis.persistence.filesystem.io._replace_file", temporarily_denied)
    atomic_write_bytes(target, b"after")
    assert calls == denials + 1
    assert target.read_bytes() == b"after"
    assert list(tmp_path.glob(".state.json.*.tmp")) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing-denial behavior")
def test_atomic_write_persistent_windows_denial_preserves_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state.json"
    target.write_bytes(b"before")
    calls = 0

    def always_denied(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        raise PermissionError(13, "sharing denied", str(destination), 5)

    monkeypatch.setattr("orqalis.persistence.filesystem.io._replace_file", always_denied)
    with pytest.raises(PermissionError, match="sharing denied"):
        atomic_write_bytes(target, b"after")
    assert calls == 5
    assert target.read_bytes() == b"before"
    assert list(tmp_path.glob(".state.json.*.tmp")) == []


@pytest.mark.parametrize("platform,winerror", [("posix", 5), ("nt", 123)])
def test_atomic_write_unknown_or_nonwindows_denial_is_immediate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str, winerror: int
) -> None:
    from orqalis.persistence.filesystem import io

    target = tmp_path / "state.json"
    target.write_bytes(b"before")
    calls: list[int] = []
    waits: list[float] = []

    def denied(source: Path, destination: Path) -> None:
        calls.append(1)
        raise PermissionError(13, "sharing denied", str(destination), winerror)

    monkeypatch.setattr(io, "os", SimpleNamespace(**{**vars(os), "name": platform}))
    monkeypatch.setattr(io, "_replace_file", denied)
    monkeypatch.setattr(io, "time", SimpleNamespace(sleep=waits.append))
    with pytest.raises(PermissionError, match="sharing denied"):
        atomic_write_bytes(target, b"after")
    assert len(calls) == 1 and not waits
    assert target.read_bytes() == b"before"
    assert list(tmp_path.glob(".state.json.*.tmp")) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing-denial behavior")
def test_atomic_write_revalidates_target_after_retry_backoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orqalis.persistence.filesystem import io

    target = tmp_path / "state.json"
    target.write_bytes(b"before")
    calls: list[int] = []
    slept = False
    guard = io.ensure_no_filesystem_links

    def denied(source: Path, destination: Path) -> None:
        calls.append(1)
        raise PermissionError(13, "sharing denied", str(destination), 32)

    def sleep(delay: float) -> None:
        nonlocal slept
        assert delay == 0.02
        slept = True

    def checked(path: Path) -> Path:
        if slept:
            raise PolicyDeniedError("Target changed during retry backoff")
        return guard(path)

    monkeypatch.setattr(io, "_replace_file", denied)
    monkeypatch.setattr(io, "time", SimpleNamespace(sleep=sleep))
    monkeypatch.setattr(io, "ensure_no_filesystem_links", checked)
    with pytest.raises(PolicyDeniedError, match="during retry backoff"):
        atomic_write_bytes(target, b"after")
    assert calls == [1]
    assert target.read_bytes() == b"before"
    assert list(tmp_path.glob(".state.json.*.tmp")) == []


def test_atomic_bytes_rejects_non_bytes_without_touching_target(tmp_path: Path) -> None:
    target = tmp_path / "value"
    target.write_bytes(b"before")
    with pytest.raises(TypeError):
        atomic_write_bytes(target, "after")  # type: ignore[arg-type]
    assert target.read_bytes() == b"before"


@pytest.mark.parametrize(
    "content",
    [b'{"key": 1, "key": 2}\n', b'{"value": NaN}\n', b"not json\n", b"[]\n"],
)
def test_validated_json_object_read_rejects_invalid_documents(
    tmp_path: Path, content: bytes
) -> None:
    path = tmp_path / "invalid.json"
    path.write_bytes(content)
    with pytest.raises(FilesystemFormatError):
        read_json_object(path)


def test_jsonl_append_is_serialized_and_validated(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    with ThreadPoolExecutor(max_workers=8) as pool:
        tuple(
            pool.map(
                lambda sequence: append_jsonl_atomic(events, {"sequence": sequence}), range(50)
            )
        )
    records = read_jsonl(events)
    assert len(records) == 50
    assert {record["sequence"] for record in records} == set(range(50))

    events.write_bytes(events.read_bytes().rstrip(b"\n"))
    with pytest.raises(FilesystemFormatError, match="incomplete"):
        read_jsonl(events)


def test_jsonl_partial_append_restores_the_committed_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events = tmp_path / "events.jsonl"
    append_jsonl_atomic(events, {"sequence": 1})
    original = os.write
    calls = 0

    def interrupted(descriptor: int, content: bytes | memoryview) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            payload = bytes(content)
            return original(descriptor, payload[: max(1, len(payload) // 2)])
        raise OSError("simulated interrupted append")

    monkeypatch.setattr(os, "write", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        append_jsonl_atomic(events, {"sequence": 2})

    assert read_jsonl(events) == ({"sequence": 1},)


def test_project_store_rejects_linked_store_and_subtrees(tmp_path: Path) -> None:
    def directory_link(link: Path, target: Path) -> None:
        if os.name == "nt":
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True,
                check=False,
            )
            if result.returncode:
                pytest.skip("Filesystem junctions are unavailable")
        else:
            link.symlink_to(target, target_is_directory=True)

    outside = tmp_path / "outside"
    outside.mkdir()
    linked_root = tmp_path / "linked-root"
    linked_root.mkdir()
    try:
        directory_link(linked_root / ".orqalis", outside)
    except OSError as exc:
        pytest.skip(f"Filesystem links are unavailable: {exc}")

    with pytest.raises(PolicyDeniedError, match="link or junction"):
        bootstrap_project_store(linked_root)
    assert not (outside / "manifest.yaml").exists()

    root = tmp_path / "repo"
    root.mkdir()
    layout = bootstrap_project_store(root)
    task_target = tmp_path / "outside-tasks"
    task_target.mkdir()
    directory_link(layout.store / "tasks", task_target)
    with pytest.raises(PolicyDeniedError, match="link or junction"):
        _ = layout.tasks


def test_file_lock_is_reentrant_and_times_out_other_threads(tmp_path: Path) -> None:
    path = tmp_path / "state.lock"
    entered = threading.Event()
    release = threading.Event()
    failures: list[BaseException] = []

    with FileLock(path):
        with FileLock(path):
            pass

        def contend() -> None:
            entered.set()
            try:
                with FileLock(path, timeout=0.05, poll_interval=0.01):
                    release.set()
            except BaseException as exc:
                failures.append(exc)

        thread = threading.Thread(target=contend)
        thread.start()
        entered.wait(timeout=1)
        thread.join(timeout=1)
        assert not release.is_set()
        assert len(failures) == 1
        assert isinstance(failures[0], LockTimeoutError)
    assert not thread.is_alive()


def test_file_lock_timeout_is_specific(tmp_path: Path) -> None:
    lock = FileLock(tmp_path / "lock", timeout=0)
    lock.acquire()
    failures: list[BaseException] = []

    def contend() -> None:
        try:
            FileLock(lock.path, timeout=0).acquire()
        except BaseException as exc:
            failures.append(exc)

    thread = threading.Thread(target=contend)
    thread.start()
    thread.join(timeout=1)
    lock.release()
    assert len(failures) == 1
    assert isinstance(failures[0], LockTimeoutError)


def _v1_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "project": {"id": "751a64c4-27b5-4d69-97ac-d4f850664169", "name": "fixture"},
        "initialized_at": "2026-09-16T14:20:00+05:30",
        "graph": {"indexed_commit": "abc123", "indexed_branch": "feature/local"},
    }


def test_manifest_missing_old_and_unsupported_schema_are_distinct(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)
    with pytest.raises(ManifestNotFoundError):
        load_manifest(layout)
    layout.store.mkdir()
    atomic_write_json(layout.manifest, _v1_manifest())
    with pytest.raises(SchemaMigrationRequired):
        load_manifest(layout)
    atomic_write_json(layout.manifest, {**_v1_manifest(), "schema_version": 99})
    with pytest.raises(UnsupportedSchemaError):
        load_manifest(layout)


def test_manifest_invalid_json_and_invalid_schema_are_rejected(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)
    layout.store.mkdir()
    layout.manifest.write_text("not-json", encoding="utf-8")
    with pytest.raises(ManifestValidationError):
        load_manifest(layout)
    atomic_write_json(
        layout.manifest,
        {
            **_v1_manifest(),
            "schema_version": 2,
            "storage": {"backend": "postgresql"},
            "graph": {"schema_version": 1},
            "memory": {"schema_version": 1},
            "tasks": {"schema_version": 1},
        },
    )
    with pytest.raises(ManifestValidationError, match="filesystem"):
        load_manifest(layout)


def test_schema_one_migration_backs_up_validates_and_updates(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)
    layout.store.mkdir()
    old = _v1_manifest()
    atomic_write_json(layout.manifest, old)
    original = layout.manifest.read_bytes()

    backup = migrate_manifest(layout)

    assert backup is not None and backup.read_bytes() == original
    migrated = load_manifest(layout)
    assert migrated["schema_version"] == 2
    assert migrated["storage"] == {"backend": "filesystem"}
    assert migrated["graph"] == {
        "schema_version": 1,
        "indexed_commit": "abc123",
        "indexed_branch": "feature/local",
    }
    assert layout.config.is_file()
    assert layout.gitignore.is_file()
    assert migrate_manifest(layout) is None


def test_idempotent_bootstrap_migrates_an_existing_schema_one_store(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)
    layout.store.mkdir()
    atomic_write_json(layout.manifest, _v1_manifest())
    durable = b'{"schema_version":1,"tasks":[]}\n'
    atomic_write_bytes(layout.tasks / "index.json", durable)

    assert bootstrap_project_store(tmp_path) == layout

    assert load_manifest(layout)["schema_version"] == 2
    assert (layout.tasks / "index.json").read_bytes() == durable
    backups = tuple((layout.store / "backups").glob("manifest.schema-1.*.yaml"))
    assert len(backups) == 1


def test_migration_rejects_invalid_old_schema_before_backup(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)
    layout.store.mkdir()
    atomic_write_json(layout.manifest, {**_v1_manifest(), "project": {"name": "missing id"}})
    with pytest.raises(ManifestValidationError):
        migrate_manifest(layout)
    assert not (layout.store / "backups").exists()


def test_migration_keeps_old_manifest_authoritative_until_final_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = ProjectLayout(tmp_path)
    layout.store.mkdir()
    atomic_write_json(layout.manifest, _v1_manifest())
    original = layout.manifest.read_bytes()
    real_atomic_write_json = atomic_write_json

    def interrupt_manifest(path: Path, value: object) -> None:
        if path == layout.manifest:
            raise OSError("simulated final manifest interruption")
        real_atomic_write_json(path, value)

    monkeypatch.setattr(
        "orqalis.persistence.filesystem.layout.atomic_write_json", interrupt_manifest
    )
    with pytest.raises(OSError, match="final manifest interruption"):
        migrate_manifest(layout)

    assert layout.manifest.read_bytes() == original
    backups = tuple((layout.store / "backups").glob("manifest.schema-1.*.yaml"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == original


def test_json_object_digest_uses_exact_single_decoded_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orqalis.persistence.filesystem import io

    path = tmp_path / "proof.json"
    content = b'{"value": "first"}\n'
    reads: list[Path] = []

    def changing_read(target: Path) -> bytes:
        reads.append(target)
        return content if len(reads) == 1 else b'{"value": "other"}\n'

    monkeypatch.setattr(io, "_read_bytes", changing_read)
    document, digest = read_json_object_with_sha256(path)
    assert document == {"value": "first"}
    assert digest == hashlib.sha256(content).hexdigest()
    assert reads == [path.absolute()]


@pytest.mark.parametrize(
    "content",
    [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b"[]", b"\xff", b"{"],
)
def test_json_object_digest_preserves_strict_decoding(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "proof.json"
    path.write_bytes(content)
    with pytest.raises(FilesystemFormatError):
        read_json_object_with_sha256(path)


@pytest.mark.parametrize("link_form", ["symlink", "junction"])
def test_storage_guard_rejects_missing_descendant_of_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, link_form: str
) -> None:
    linked_parent = tmp_path / "linked"
    candidate = linked_parent / "missing" / "document.json"
    native_lstat = Path.lstat

    def metadata(path: Path) -> os.stat_result:
        if path == linked_parent:
            return cast(
                os.stat_result,
                SimpleNamespace(
                    st_mode=stat.S_IFLNK if link_form == "symlink" else stat.S_IFDIR,
                    st_reparse_tag=0 if link_form == "symlink" else 0xA0000003,
                ),
            )
        return native_lstat(path)

    monkeypatch.setattr(Path, "lstat", metadata)
    with pytest.raises(PolicyDeniedError, match="link or junction"):
        ensure_no_filesystem_links(candidate)


@pytest.mark.parametrize("failure", [PermissionError("denied"), OSError("metadata unavailable")])
def test_storage_guard_preserves_unexpected_metadata_errors_before_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: OSError
) -> None:
    target = tmp_path / "document.json"
    original = b'{"original": true}\n'
    target.write_bytes(original)
    native_lstat = Path.lstat

    def metadata(path: Path) -> os.stat_result:
        if path == target:
            raise failure
        return native_lstat(path)

    monkeypatch.setattr(Path, "lstat", metadata)
    with pytest.raises(OSError) as caught:
        atomic_write_json(target, {"changed": True})
    assert caught.value is failure
    assert target.read_bytes() == original


def test_storage_guard_allows_missing_regular_descendants(tmp_path: Path) -> None:
    target = tmp_path / "missing" / "nested" / "document.json"
    assert ensure_no_filesystem_links(target) == target.absolute()
    assert not target.exists()


def _wait_for_gate_queue(gate: _ReentrantGate, count: int) -> None:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        with gate._condition:
            if len(gate._waiters) == count:
                return
        time.sleep(0.001)
    raise AssertionError("Waiter did not reach the controlled queue barrier")


def test_queued_waiter_prevents_owner_barging_and_preserves_reentry() -> None:
    gate = _ReentrantGate()
    assert gate.acquire(timeout=0)
    entered, release = threading.Event(), threading.Event()
    outcomes: list[bool] = []

    def queued() -> None:
        acquired = gate.acquire(timeout=2)
        outcomes.append(acquired)
        if acquired:
            try:
                entered.set()
                assert release.wait(2)
            finally:
                gate.release()

    worker = threading.Thread(target=queued)
    worker.start()
    try:
        _wait_for_gate_queue(gate, 1)
        assert gate.acquire(timeout=0)
        gate.release()
        assert not entered.is_set()
        gate.release()
        assert not gate.acquire(timeout=0)
        assert entered.wait(2)
    finally:
        release.set()
        worker.join(2)
    assert not worker.is_alive()
    assert outcomes == [True]
    assert gate.acquire(timeout=0)
    gate.release()


def test_expired_head_waiter_does_not_block_its_successor() -> None:
    gate = _ReentrantGate()
    assert gate.acquire(timeout=0)
    outcomes: list[tuple[str, bool]] = []

    def contend(name: str, timeout: float) -> None:
        acquired = gate.acquire(timeout=timeout)
        outcomes.append((name, acquired))
        if acquired:
            gate.release()

    first = threading.Thread(target=contend, args=("expired", 0.1))
    second = threading.Thread(target=contend, args=("successor", 2))
    first.start()
    _wait_for_gate_queue(gate, 1)
    second.start()
    try:
        _wait_for_gate_queue(gate, 2)
        first.join(1)
        assert not first.is_alive()
        _wait_for_gate_queue(gate, 1)
    finally:
        gate.release()
        first.join(2)
        second.join(2)
    assert not second.is_alive()
    assert outcomes == [("expired", False), ("successor", True)]


def test_bookkeeping_mutex_obeys_acquisition_timeout() -> None:
    gate = _ReentrantGate()
    outcomes: list[bool] = []
    with gate._condition:
        worker = threading.Thread(target=lambda: outcomes.append(gate.acquire(timeout=0.05)))
        worker.start()
        worker.join(1)
        assert not worker.is_alive()
        assert outcomes == [False]
    assert gate.acquire(timeout=0)
    gate.release()


def test_interrupted_wait_removes_its_queue_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    gate = _ReentrantGate()
    assert gate.acquire(timeout=0)
    errors: list[BaseException] = []

    def interrupted(timeout: float | None = None) -> bool:
        raise OSError("controlled wait interruption")

    monkeypatch.setattr(gate._condition, "wait", interrupted)

    def contend() -> None:
        try:
            gate.acquire(timeout=1)
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=contend)
    worker.start()
    worker.join(1)
    assert not worker.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], OSError)
    assert not gate._waiters
    gate.release()
    assert gate.acquire(timeout=0)
    gate.release()


@pytest.mark.parametrize(
    ("timeout", "error"),
    [
        (float("nan"), ValueError),
        (float("inf"), OverflowError),
        (threading.TIMEOUT_MAX * 2, OverflowError),
    ],
)
def test_invalid_timeout_retains_rlock_rejection(timeout: float, error: type[Exception]) -> None:
    gate = _ReentrantGate()
    with pytest.raises(error):
        gate.acquire(timeout=timeout)
    assert gate.acquire(timeout=0)
    gate.release()


def test_zero_timeout_owner_reentry_ignores_waiter_bookkeeping_mutex() -> None:
    gate = _ReentrantGate()
    assert gate.acquire(timeout=0)
    entered, release = threading.Event(), threading.Event()

    def hold_bookkeeping() -> None:
        with gate._condition:
            entered.set()
            assert release.wait(2)

    worker = threading.Thread(target=hold_bookkeeping)
    worker.start()
    try:
        assert entered.wait(2)
        assert gate.acquire(timeout=0)
    finally:
        release.set()
        worker.join(2)
    assert not worker.is_alive()
    gate.release()
    gate.release()
    assert gate.acquire(timeout=0)
    gate.release()


@pytest.mark.parametrize("parts", [(), ("memory",), ("tasks", "safe", "state.json")])
def test_layout_descendant_uses_one_fresh_full_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parts: tuple[str, ...]
) -> None:
    from orqalis.persistence.filesystem import layout as layout_module

    layout = ProjectLayout(tmp_path)
    store = tmp_path / ".orqalis"
    calls: list[Path] = []
    native = ensure_no_filesystem_links

    def guarded(path: Path) -> Path:
        calls.append(path)
        return native(path)

    monkeypatch.setattr(layout_module, "ensure_no_filesystem_links", guarded)
    assert layout._storage_path(*parts) == store.joinpath(*parts)
    assert calls == [store.joinpath(*parts)]
    assert layout._storage_path(*parts) == store.joinpath(*parts)
    assert calls == [store.joinpath(*parts)] * 2


@pytest.mark.parametrize("component", ["store", "parent", "target"])
@pytest.mark.parametrize("link_form", ["symlink", "junction"])
def test_layout_descendant_full_guard_rejects_new_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, component: str, link_form: str
) -> None:
    layout = ProjectLayout(tmp_path)
    store = tmp_path / ".orqalis"
    target = store / "memory" / "state.json"
    assert layout._storage_path("memory", "state.json") == target
    linked = {"store": store, "parent": target.parent, "target": target}[component]
    native_lstat = Path.lstat

    def metadata(path: Path) -> os.stat_result:
        if path == linked:
            return cast(
                os.stat_result,
                SimpleNamespace(
                    st_mode=stat.S_IFLNK if link_form == "symlink" else stat.S_IFDIR,
                    st_reparse_tag=0 if link_form == "symlink" else 0xA0000003,
                ),
            )
        return native_lstat(path)

    monkeypatch.setattr(Path, "lstat", metadata)
    with pytest.raises(PolicyDeniedError, match="link or junction"):
        layout._storage_path("memory", "state.json")


def test_layout_arbitrary_parts_keep_store_guard_before_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from orqalis.persistence.filesystem import layout as layout_module

    layout = ProjectLayout(tmp_path)
    store = tmp_path / ".orqalis"
    cases = [(str(tmp_path / "outside"),), ("..", "outside"), ("memory", "..", "state.json")]
    if os.name == "nt":
        cases.extend([(r"\outside",), ("Z:relative",)])
    native = ensure_no_filesystem_links
    for parts in cases:
        calls: list[Path] = []

        def guarded(path: Path, calls: list[Path] = calls) -> Path:
            calls.append(path)
            return native(path)

        monkeypatch.setattr(layout_module, "ensure_no_filesystem_links", guarded)
        candidate = store.joinpath(*parts)
        resolved = candidate.resolve(strict=False)
        if resolved == store or resolved.is_relative_to(store):
            assert layout._storage_path(*parts) == candidate.absolute()
        else:
            with pytest.raises(PolicyDeniedError, match="escapes"):
                layout._storage_path(*parts)
        assert calls == [store, candidate]


def test_layout_absolute_escape_cannot_bypass_linked_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = ProjectLayout(tmp_path)
    store = tmp_path / ".orqalis"
    outside = tmp_path / "outside"
    native_lstat = Path.lstat

    def metadata(path: Path) -> os.stat_result:
        if path == store:
            return cast(
                os.stat_result, SimpleNamespace(st_mode=stat.S_IFDIR, st_reparse_tag=0xA0000003)
            )
        return native_lstat(path)

    monkeypatch.setattr(Path, "lstat", metadata)
    with pytest.raises(PolicyDeniedError, match="link or junction"):
        layout._storage_path(str(outside))


def test_layout_subclass_store_dispatch_precedes_root_and_parts(tmp_path: Path) -> None:
    class DeniedLayout(ProjectLayout):
        blocked = False

        @property
        def store(self) -> Path:
            raise PolicyDeniedError("custom store denied")

        def __getattribute__(self, name: str) -> object:
            if name == "root" and object.__getattribute__(self, "blocked"):
                raise AssertionError("root accessed before store")
            return object.__getattribute__(self, name)

    layout = DeniedLayout(tmp_path)
    object.__setattr__(layout, "blocked", True)
    with pytest.raises(PolicyDeniedError, match="custom store denied"):
        layout._storage_path("memory")


def test_layout_subclass_custom_store_is_retained(tmp_path: Path) -> None:
    custom = tmp_path / "custom"

    class CustomLayout(ProjectLayout):
        @property
        def store(self) -> Path:
            return ensure_no_filesystem_links(custom)

    assert CustomLayout(tmp_path)._storage_path("memory") == custom / "memory"


@pytest.mark.parametrize("failure", [PermissionError("denied"), OSError("metadata unavailable")])
def test_layout_descendant_propagates_metadata_faults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: OSError
) -> None:
    layout = ProjectLayout(tmp_path)
    store = tmp_path / ".orqalis"
    native_lstat = Path.lstat

    def metadata(path: Path) -> os.stat_result:
        if path == store:
            raise failure
        return native_lstat(path)

    monkeypatch.setattr(Path, "lstat", metadata)
    with pytest.raises(OSError) as caught:
        layout._storage_path("memory", "state.json")
    assert caught.value is failure


@pytest.mark.parametrize("relative_root", [True, False])
def test_layout_noncanonical_root_keeps_resolution_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative_root: bool
) -> None:
    layout = ProjectLayout(tmp_path)
    monkeypatch.chdir(tmp_path)
    root = Path("relative-repo") if relative_root else tmp_path / "unused" / ".." / "repo"
    object.__setattr__(layout, "root", root)
    assert (
        layout._storage_path("memory", "state.json")
        == (root / ".orqalis" / "memory" / "state.json").absolute()
    )


def test_layout_rejects_candidate_resolved_outside_after_fresh_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = ProjectLayout(tmp_path)
    target = tmp_path / ".orqalis" / "memory" / "state.json"
    native = Path.resolve

    def resolve(path: Path, strict: bool = False) -> Path:
        if path == target:
            return tmp_path / "outside" / "state.json"
        return native(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(PolicyDeniedError, match="escapes"):
        layout._storage_path("memory", "state.json")


def test_layout_custom_path_keeps_store_resolution_failure(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)
    native = Path.resolve

    def resolve(path: Path, strict: bool = False) -> Path:
        if path.name == ".orqalis":
            raise PermissionError("custom store resolution denied")
        return native(path, strict=strict)

    custom_path = type("CustomStorePath", (type(tmp_path),), {"resolve": resolve})
    object.__setattr__(layout, "root", custom_path(tmp_path))
    with pytest.raises(PermissionError, match="custom store resolution denied"):
        layout._storage_path("memory", "state.json")


@pytest.mark.skipif(os.name != "nt", reason="Native Windows readonly replacement/cleanup")
def test_atomic_readonly_target_denial_keeps_original_error_and_cleans_temp(
    tmp_path: Path,
) -> None:
    target = tmp_path / "readonly.json"
    target.write_bytes(b"before")
    target.chmod(0o444)
    before = target.stat()
    try:
        with pytest.raises(PermissionError) as denied:
            atomic_write_bytes(target, b"after")
        assert getattr(denied.value, "winerror", None) == 5
        assert denied.value.filename2 == str(target)
        assert target.read_bytes() == b"before"
        after = target.stat()
        assert stat.S_IMODE(after.st_mode) == stat.S_IMODE(before.st_mode)
        assert getattr(after, "st_file_attributes", 0) == getattr(before, "st_file_attributes", 0)
        assert getattr(after, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_READONLY
        assert list(tmp_path.glob(".readonly.json.*.tmp")) == []
    finally:
        target.chmod(stat.S_IREAD | stat.S_IWRITE)
        for temporary in tmp_path.glob(".readonly.json.*.tmp"):
            temporary.chmod(stat.S_IREAD | stat.S_IWRITE)
            temporary.unlink()


@pytest.mark.skipif(os.name != "nt", reason="Native Windows readonly temporary cleanup")
def test_atomic_explicit_readonly_temp_keeps_writable_target_and_replace_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "explicit.json"
    target.write_bytes(b"before")
    original_mode = stat.S_IMODE(target.stat().st_mode)
    replacement_error = OSError("replacement refused")
    chmod = os.chmod
    changed: list[Path] = []

    def denied(source: Path, destination: Path) -> None:
        raise replacement_error

    def tracked_chmod(path: Path, mode: int) -> None:
        changed.append(path)
        chmod(path, mode)

    monkeypatch.setattr("orqalis.persistence.filesystem.io._replace_file", denied)
    monkeypatch.setattr("orqalis.persistence.filesystem.io.os.chmod", tracked_chmod)
    with pytest.raises(OSError) as caught:
        atomic_write_bytes(target, b"after", mode=0o444)
    assert caught.value is replacement_error
    assert target.read_bytes() == b"before"
    assert stat.S_IMODE(target.stat().st_mode) == original_mode
    assert list(tmp_path.glob(".explicit.json.*.tmp")) == []
    assert len(changed) == 2 and all(path != target for path in changed)


@pytest.mark.parametrize(
    "platform,winerror,readonly,regular",
    [
        ("posix", 5, True, True),
        ("nt", 32, True, True),
        ("nt", 123, True, True),
        ("nt", 5, False, True),
        ("nt", 5, True, False),
    ],
)
def test_atomic_cleanup_unrelated_denials_do_not_chmod_or_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    winerror: int,
    readonly: bool,
    regular: bool,
) -> None:
    from orqalis.persistence.filesystem import io

    target = tmp_path / "classification.json"
    target.write_bytes(b"before")
    cleanup_error = PermissionError("cleanup denied")
    monkeypatch.setattr(cleanup_error, "winerror", winerror, raising=False)
    replacement_error = OSError("replacement refused")
    chmod = os.chmod
    lstat = Path.lstat
    unlink = Path.unlink
    unlink_calls: list[Path] = []
    chmod_calls: list[Path] = []

    def is_temporary(path: Path) -> bool:
        return path.parent == tmp_path and path.name.startswith(".classification.json.")

    def denied(source: Path, destination: Path) -> None:
        raise replacement_error

    def tracked_chmod(path: Path, mode: int) -> None:
        chmod_calls.append(path)
        chmod(path, mode)

    def denied_unlink(path: Path, missing_ok: bool = False) -> None:
        if is_temporary(path):
            unlink_calls.append(path)
            raise cleanup_error
        unlink(path, missing_ok=missing_ok)

    def metadata(path: Path, *args: object, **kwargs: object) -> os.stat_result:
        if is_temporary(path):
            return cast(
                os.stat_result,
                SimpleNamespace(
                    st_mode=(stat.S_IFREG if regular else stat.S_IFDIR) | 0o644,
                    st_file_attributes=0x1 if readonly else 0,
                    st_reparse_tag=0,
                ),
            )
        return lstat(path)

    with monkeypatch.context() as scoped:
        scoped.setattr(io, "os", SimpleNamespace(**{**vars(os), "name": platform}))
        scoped.setattr("orqalis.persistence.filesystem.io._replace_file", denied)
        scoped.setattr("orqalis.persistence.filesystem.io.os.chmod", tracked_chmod)
        scoped.setattr(Path, "unlink", denied_unlink)
        scoped.setattr(Path, "lstat", metadata)
        with pytest.raises(PermissionError) as caught:
            atomic_write_bytes(target, b"after")
        assert caught.value is cleanup_error
        assert len(unlink_calls) == 1 and len(chmod_calls) == 1
    assert target.read_bytes() == b"before"
    temporaries = list(tmp_path.glob(".classification.json.*.tmp"))
    assert len(temporaries) == 1
    for temporary in temporaries:
        temporary.chmod(stat.S_IREAD | stat.S_IWRITE)
        temporary.unlink()


@pytest.mark.skipif(os.name != "nt", reason="Windows cleanup policy guard path")
def test_atomic_cleanup_guard_rejection_prevents_fallback_chmod(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from orqalis.persistence.filesystem import io

    target = tmp_path / "guard.json"
    target.write_bytes(b"before")
    guard = io.ensure_no_filesystem_links
    chmod = os.chmod
    calls: list[Path] = []
    replacement_error = OSError("replacement refused")

    def denied(source: Path, destination: Path) -> None:
        raise replacement_error

    def rejected(path: Path) -> Path:
        if path.name.startswith(".guard.json."):
            raise PolicyDeniedError("temporary guard rejected")
        return guard(path)

    def tracked_chmod(path: Path, mode: int) -> None:
        calls.append(path)
        chmod(path, mode)

    with monkeypatch.context() as scoped:
        scoped.setattr("orqalis.persistence.filesystem.io._replace_file", denied)
        scoped.setattr("orqalis.persistence.filesystem.io.os.chmod", tracked_chmod)
        scoped.setattr(io, "ensure_no_filesystem_links", rejected)
        with pytest.raises(PolicyDeniedError, match="temporary guard rejected"):
            atomic_write_bytes(target, b"after", mode=0o444)
        assert len(calls) == 1 and target not in calls
    assert target.read_bytes() == b"before"
    for temporary in tmp_path.glob(".guard.json.*.tmp"):
        temporary.chmod(stat.S_IREAD | stat.S_IWRITE)
        temporary.unlink()


def test_atomic_success_keeps_one_unlink_and_no_temp_lstat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "success.json"
    unlink = Path.unlink
    lstat = Path.lstat
    unlink_calls: list[Path] = []
    lstat_calls: list[Path] = []

    def tracked_unlink(path: Path, missing_ok: bool = False) -> None:
        if path.name.startswith(".success.json."):
            unlink_calls.append(path)
        unlink(path, missing_ok=missing_ok)

    def tracked_lstat(path: Path, *args: object, **kwargs: object) -> os.stat_result:
        if path.name.startswith(".success.json."):
            lstat_calls.append(path)
        return lstat(path)

    monkeypatch.setattr(Path, "unlink", tracked_unlink)
    monkeypatch.setattr(Path, "lstat", tracked_lstat)
    atomic_write_bytes(target, b"after")
    assert target.read_bytes() == b"after"
    assert len(unlink_calls) == 1 and lstat_calls == []
    assert list(tmp_path.glob(".success.json.*.tmp")) == []
