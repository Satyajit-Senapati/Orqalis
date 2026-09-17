from pathlib import Path

import pytest

from orqalis.domain.errors import ConflictError, InputError, NotFoundError
from orqalis.domain.project import Project
from orqalis.domain.run import Run
from orqalis.persistence.filesystem.io import atomic_write_json, read_json_object
from orqalis.persistence.filesystem.layout import ProjectLayout, load_manifest
from orqalis.persistence.filesystem.task_store import TaskCapsuleStore
from orqalis.tasks.history import TaskHistoryService


def history_fixture(root: Path, request: str = "Implement tablet navigation") -> tuple[str, Run]:
    root.mkdir()
    store = TaskCapsuleStore.from_root(root)
    project = Project(name=root.name, repo_root=root, default_branch="main")
    run = Run(
        project_id=project.id,
        request=request,
        target_branch="feature/navigation",
        base_commit="a" * 40,
    )
    with store.unit_of_work() as uow:
        uow.projects.add(project)
        uow.runs.add(run)
        uow.commit()
    task_id = store.capsule_id(run.id)
    assert task_id is not None
    return task_id, run


def test_history_lists_and_reads_capsule_after_index_deletion(tmp_path: Path) -> None:
    task_id, run = history_fixture(tmp_path / "repo")
    service = TaskHistoryService(tmp_path / "repo")
    (service.layout.tasks / "index.json").unlink()

    entries = service.list()
    view = service.get(task_id)
    assert entries[0].id == task_id
    assert entries[0].run_id == run.id
    assert view.request == run.request
    assert view.event_count == 0
    assert "task.yaml" in view.files
    assert service.get_by_run(run.id).task.id == task_id


def test_history_related_tasks_are_selective(tmp_path: Path) -> None:
    first, _ = history_fixture(tmp_path / "repo", "Implement tablet navigation")
    service = TaskHistoryService(tmp_path / "repo")
    assert [entry.id for entry in service.related("tablet navigation")] == [first]
    assert service.related("unrelated phrase") == ()


def test_history_isolated_by_repository_and_rejects_unsafe_ids(tmp_path: Path) -> None:
    _, run_a = history_fixture(tmp_path / "repo-a")
    store_a = TaskCapsuleStore.from_root(tmp_path / "repo-a")
    second = Run(
        project_id=run_a.project_id,
        request="Only repository A knows this task",
        target_branch="feature/only-a",
        base_commit="b" * 40,
    )
    with store_a.unit_of_work() as uow:
        uow.runs.add(second)
        uow.commit()
    task_a = store_a.capsule_id(second.id)
    assert task_a is not None
    history_fixture(tmp_path / "repo-b")
    service_b = TaskHistoryService(tmp_path / "repo-b")

    with pytest.raises(NotFoundError):
        service_b.get(task_a)
    with pytest.raises(InputError):
        service_b.get("../repo-a/.orqalis/tasks/" + task_a)


def test_history_derives_acceptance_and_wraps_malformed_run_ids(tmp_path: Path) -> None:
    task_id, _ = history_fixture(tmp_path / "repo")
    service = TaskHistoryService(tmp_path / "repo")
    capsule = service.layout.task(task_id)
    atomic_write_json(
        capsule / "review" / "acceptance-results.yaml",
        {"criteria": [{"status": "PASS"}, {"status": "TESTING"}]},
    )
    assert service.get(task_id).task.acceptance_result == "PENDING"
    atomic_write_json(
        capsule / "review" / "acceptance-results.yaml",
        {"criteria": [{"status": "PASS"}, {"status": "FAIL"}]},
    )
    assert service.get(task_id).task.acceptance_result == "FAIL"

    metadata = read_json_object(capsule / "task.yaml")
    metadata["run_id"] = "not-a-uuid"
    atomic_write_json(capsule / "task.yaml", metadata)
    with pytest.raises(ConflictError, match="run ID"):
        service.get(task_id)


def test_history_open_migrates_schema_one_before_loading_tasks(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    layout = ProjectLayout(root)
    layout.store.mkdir()
    atomic_write_json(
        layout.manifest,
        {
            "schema_version": 1,
            "project": {
                "id": "751a64c4-27b5-4d69-97ac-d4f850664169",
                "name": "fixture",
            },
            "initialized_at": "2026-09-16T14:20:00+05:30",
            "graph": {"indexed_commit": "abc123", "indexed_branch": "main"},
        },
    )

    service = TaskHistoryService(root)

    assert service.list() == ()
    assert load_manifest(layout)["schema_version"] == 2
