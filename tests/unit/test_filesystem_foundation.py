from __future__ import annotations

import json
import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
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

    monkeypatch.setattr("orqalis.persistence.filesystem.io.os.replace", fail_replace)
    with pytest.raises(OSError, match="simulated interruption"):
        atomic_write_json(target, {"state": "after"})
    assert read_json_object(target) == {"state": "before"}
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
