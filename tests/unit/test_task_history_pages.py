import base64
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from orqalis.domain.errors import ConflictError, InputError, PolicyDeniedError
from orqalis.domain.project import Project
from orqalis.domain.run import Run
from orqalis.persistence.filesystem.task_store import TaskCapsuleStore
from orqalis.tasks.history import TaskHistoryService
from tests.unit.test_task_history import history_fixture


def fixture(root: Path, count: int = 5) -> TaskHistoryService:
    _, first = history_fixture(root)
    store = TaskCapsuleStore.from_root(root)
    for index in range(1, count):
        # Equal timestamps exercise the capsule-ID tie-breaker, not filesystem order.
        run = first.model_copy(update={"id": uuid4(), "request": f"Task {index}"})
        with store.unit_of_work() as uow:
            uow.runs.add(run)
            uow.commit()
    return TaskHistoryService(root)


def test_pages_cover_equal_timestamp_history_without_duplicates_after_reopen(
    tmp_path: Path,
) -> None:
    service = fixture(tmp_path / "repo")
    expected = service.list()
    first = service.page(2)
    assert first.total == 5 and len(first.items) == 2 and first.next_cursor
    assert [item.id for item in first.items] == [item.id for item in expected[:2]]
    reopened = TaskHistoryService(service.root)
    second = reopened.page(2, first.next_cursor)
    assert second.revision == first.revision and second.next_cursor
    final = reopened.page(2, second.next_cursor)
    assert final.next_cursor is None and len(final.items) == 1
    items = (*first.items, *second.items, *final.items)
    assert [item.id for item in items] == [item.id for item in expected]
    assert len({item.id for item in items}) == 5
    assert reopened.page(100).next_cursor is None


def test_cursor_rejects_copied_project_root_and_stale_revision(tmp_path: Path) -> None:
    service = fixture(tmp_path / "repo")
    first = service.page(2)
    assert first.next_cursor
    copied = tmp_path / "copied"
    shutil.copytree(service.root, copied)
    with pytest.raises(PolicyDeniedError, match="another project root"):
        TaskHistoryService(copied).page(2, first.next_cursor)
    run = Run(
        project_id=first.items[0].run_id,
        request="A new task",
        target_branch="feature/new",
        base_commit="a" * 40,
    )
    with service.store.unit_of_work() as uow:
        project = uow.projects.list()[0]
        uow.runs.add(run.model_copy(update={"project_id": project.id}))
        uow.commit()
    with pytest.raises(ConflictError, match="restart pagination"):
        service.page(2, first.next_cursor)
    assert service.page(2).total == 6


def test_page_rejects_invalid_cursor_and_bounds_without_unbounded_stage_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = fixture(tmp_path / "repo")
    monkeypatch.setattr(service, "_agents", lambda _: pytest.fail("Full capsule stages loaded"))
    first = service.page(1)
    assert first.next_cursor
    for cursor in ("", "!", "a" * 1025, "e30", "_w"):
        with pytest.raises(InputError, match="cursor"):
            service.page(1, cursor)
    payload = json.loads(
        base64.urlsafe_b64decode(first.next_cursor + "=" * (-len(first.next_cursor) % 4))
    )
    payload["offset"] = 10000
    invalid = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    with pytest.raises(InputError, match="position"):
        service.page(1, invalid)
    for limit in (0, 101):
        with pytest.raises(InputError, match="limit"):
            service.page(limit)


def test_empty_page_returns_no_continuation(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    store = TaskCapsuleStore.from_root(root)
    with store.unit_of_work() as uow:
        uow.projects.add(Project(name="empty", repo_root=root, default_branch="main"))
        uow.commit()
    service = TaskHistoryService(root)
    page = service.page()
    assert page.items == () and page.total == 0 and page.next_cursor is None


def test_unchanged_pages_do_not_replace_the_derived_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = fixture(tmp_path / "repo")
    first = service.page(2)
    index = service.layout.tasks / "index.json"
    original = index.read_bytes()
    modified = index.stat().st_mtime_ns

    def unexpected_write(*args: object, **kwargs: object) -> None:
        pytest.fail("Unchanged history replaced the derived index")

    monkeypatch.setattr(
        "orqalis.persistence.filesystem.task_store.atomic_write_json", unexpected_write
    )
    assert service.page(2, first.next_cursor).revision == first.revision
    assert len(service.list()) == 5
    assert index.read_bytes() == original
    assert index.stat().st_mtime_ns == modified


def test_same_size_same_timestamp_edit_invalidates_cursor(tmp_path: Path) -> None:
    service = fixture(tmp_path / "repo")
    first = service.page(2)
    task = service.layout.task(first.items[0].id) / "task.yaml"
    before = task.stat()
    content = task.read_bytes()
    title = first.items[0].title.encode()
    replacement = b"X" * len(title)
    assert title != replacement and title in content
    edited = content.replace(title, replacement)
    assert len(edited) == len(content)
    task.write_bytes(edited)
    os.utime(task, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert task.stat().st_mtime_ns == before.st_mtime_ns
    with pytest.raises(ConflictError, match="restart pagination"):
        service.page(2, first.next_cursor)
    fresh = service.page(100)
    assert fresh.revision != first.revision
    assert next(item for item in fresh.items if item.id == first.items[0].id).title == (
        replacement.decode()
    )


@pytest.mark.parametrize("index_contents", [None, b"{broken", b'{"tasks": []}'])
def test_pages_repair_missing_or_corrupt_index_from_canonical_tasks(
    tmp_path: Path, index_contents: bytes | None
) -> None:
    service = fixture(tmp_path / "repo")
    expected = service.page(100)
    index = service.layout.tasks / "index.json"
    if index_contents is None:
        index.unlink()
    else:
        index.write_bytes(index_contents)
    assert service.page(100) == expected
    assert len(json.loads(index.read_text())["tasks"]) == 5
    (service.layout.task(expected.items[0].id) / "task.yaml").write_bytes(b"{broken")
    with pytest.raises(ConflictError, match="metadata is invalid"):
        service.page(100)


def test_slow_canonical_scan_does_not_block_task_allocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = fixture(tmp_path / "repo")
    scanning = Event()
    release = Event()
    original = service.store._task_document

    def blocked_read(path: Path) -> dict[str, object] | None:
        if not scanning.is_set():
            scanning.set()
            assert release.wait(5), "History test barrier was not released"
        return original(path)

    monkeypatch.setattr(service.store, "_task_document", blocked_read)
    with ThreadPoolExecutor(max_workers=3) as pool:
        page_future = pool.submit(service.page, 2)
        try:
            assert scanning.wait(3)
            first = pool.submit(service.store.reserve_capsule)
            second = pool.submit(service.store.reserve_capsule)
            first_id, first_path = first.result(timeout=3)
            second_id, second_path = second.result(timeout=3)
            assert first_id != second_id
            assert first_path.is_dir() and second_path.is_dir()
            assert not release.is_set()
        finally:
            release.set()
        assert page_future.result(timeout=3).total == 5


def test_concurrent_canonical_commit_repairs_a_stale_scan_on_next_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = fixture(tmp_path / "repo")
    scanned = Event()
    release = Event()
    original = service.store._task_document
    final_capsule = service.store._capsule_directories()[-1]

    def blocked_after_read(path: Path) -> dict[str, object] | None:
        result = original(path)
        if path == final_capsule and not scanned.is_set():
            scanned.set()
            assert release.wait(5), "History test barrier was not released"
        return result

    monkeypatch.setattr(service.store, "_task_document", blocked_after_read)
    with ThreadPoolExecutor(max_workers=2) as pool:
        page_future = pool.submit(service.page, 2)
        try:
            assert scanned.wait(3)
            other = TaskCapsuleStore.from_root(service.root)

            def commit_new_run() -> Run:
                with other.unit_of_work() as uow:
                    project = uow.projects.list()[0]
                    run = Run(
                        project_id=project.id,
                        request="Concurrent task",
                        target_branch="feature/concurrent",
                        base_commit="a" * 40,
                    )
                    uow.runs.add(run)
                    uow.commit()
                return run

            run = pool.submit(commit_new_run).result(timeout=3)
        finally:
            release.set()
        old_page = page_future.result(timeout=3)
    assert old_page.total == 5 and old_page.next_cursor
    assert other.capsule_id(run.id) is not None
    with pytest.raises(ConflictError, match="restart pagination"):
        service.page(2, old_page.next_cursor)
    fresh = service.page(100)
    assert fresh.total == 6 and any(item.run_id == run.id for item in fresh.items)
    assert len(json.loads((service.layout.tasks / "index.json").read_text())["tasks"]) == 6
