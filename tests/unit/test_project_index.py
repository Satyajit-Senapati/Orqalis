import os
import shutil
import subprocess
from pathlib import Path

from orqalis.indexing import IndexManifest, IndexRecordKind, ProjectIndex
from orqalis.memory.curated import CuratedMemoryStore, MemoryCategory, MemoryProvenance
from orqalis.persistence.filesystem import (
    ProjectLayout,
    atomic_write_bytes,
    atomic_write_json,
    bootstrap_project_store,
    read_json_object,
    read_jsonl,
)


def _git(path: Path, *args: str) -> str:
    environment = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Index Test",
        "GIT_AUTHOR_EMAIL": "index@example.invalid",
        "GIT_COMMITTER_NAME": "Index Test",
        "GIT_COMMITTER_EMAIL": "index@example.invalid",
    }
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        env=environment,
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def _project(tmp_path: Path, name: str, function_name: str) -> Path:
    root = tmp_path / name
    root.mkdir()
    _git(root, "init", "-b", "main")
    (root / "sync.py").write_text(
        f"class SyncCoordinator:\n    def {function_name}(self):\n        return 'ready'\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(f"# {name}\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture")
    bootstrap_project_store(root, project_name=name)
    return root


def _memory(root: Path, title: str, content: str) -> None:
    store = CuratedMemoryStore(ProjectLayout(root))
    store.save(
        store.new_record(
            MemoryCategory.PITFALLS,
            title,
            content,
            MemoryProvenance(type="repository", paths=("sync.py",)),
            verified_commit=_git(root, "rev-parse", "HEAD"),
        )
    )


def _task(root: Path) -> str:
    task_id = "ORQ-20260916-0001"
    capsule = ProjectLayout(root).task(task_id)
    (capsule / "final").mkdir(parents=True)
    atomic_write_json(
        capsule / "task.yaml",
        {
            "schema_version": 1,
            "id": task_id,
            "run_id": "00000000-0000-0000-0000-000000000001",
            "title": "Repair tablet navigation",
            "status": "COMPLETED",
            "created_at": "2026-09-16T08:00:00+00:00",
            "completed_at": "2026-09-16T09:00:00+00:00",
            "project": {"branch": "main", "starting_commit": _git(root, "rev-parse", "HEAD")},
        },
    )
    atomic_write_bytes(
        capsule / "final" / "summary.md",
        b"Adjusted the tablet navigation rail breakpoint and preserved back behavior.\n",
    )
    return task_id


def test_rebuild_generates_all_artifacts_and_searches_each_source(tmp_path: Path) -> None:
    root = _project(tmp_path, "nevri", "retry_offline")
    _memory(
        root,
        "Offline retry durability",
        "Retry state must survive process resurrection and reconnect safely.",
    )
    task_id = _task(root)

    result = ProjectIndex(root).rebuild()
    layout = ProjectLayout(root)
    expected = {
        "manifest.json",
        "files.jsonl",
        "symbols.jsonl",
        "relations.jsonl",
        "terms.json",
        "task-index.json",
    }
    assert {path.name for path in layout.index.iterdir()} == expected
    assert read_jsonl(layout.index / "files.jsonl")
    assert read_jsonl(layout.index / "symbols.jsonl")
    assert read_jsonl(layout.index / "relations.jsonl")

    manifest = IndexManifest.model_validate(read_json_object(layout.index / "manifest.json"))
    assert manifest.project_name == "nevri"
    assert set(manifest.artifacts) == expected - {"manifest.json"}
    assert manifest.metrics == result.metrics
    assert result.metrics.documents_indexed > result.metrics.file_records
    assert result.metrics.terms_indexed > 0
    assert result.metrics.memory_records == 1
    assert result.metrics.task_records == 1

    task_index = read_json_object(layout.index / "task-index.json")
    assert task_index["tasks"][0]["id"] == task_id  # type: ignore[index]
    index = ProjectIndex(root)
    assert index.search("retry_offline")[0].document.kind == IndexRecordKind.SYMBOL
    assert index.search("process resurrection")[0].document.kind == IndexRecordKind.MEMORY
    assert index.search("tablet breakpoint")[0].document.kind == IndexRecordKind.TASK


def test_search_rebuilds_deleted_index_after_cache_deletion(tmp_path: Path) -> None:
    root = _project(tmp_path, "recoverable", "resume_sync")
    _memory(root, "Restart recovery", "Resume sync after a cold restart.")
    index = ProjectIndex(root)
    index.rebuild()
    layout = ProjectLayout(root)

    shutil.rmtree(layout.index)
    shutil.rmtree(layout.cache)

    matches = index.search("cold restart")
    assert matches[0].document.kind == IndexRecordKind.MEMORY
    assert (layout.index / "manifest.json").is_file()
    assert (layout.index / "terms.json").is_file()
    assert any((layout.cache / "parser").iterdir())


def test_indexes_are_strictly_isolated_by_repository_root(tmp_path: Path) -> None:
    first = _project(tmp_path, "first", "first_repository_symbol")
    second = _project(tmp_path, "second", "second_repository_symbol")
    _memory(first, "First-only protocol", "Use the heliotrope retry protocol.")
    _memory(second, "Second-only protocol", "Use the vermilion retry protocol.")

    first_index = ProjectIndex(first)
    second_index = ProjectIndex(second)
    first_index.rebuild()
    second_index.rebuild()

    assert first_index.search("heliotrope")
    assert not first_index.search("vermilion")
    assert second_index.search("vermilion")
    assert not second_index.search("heliotrope")
    first_manifest = IndexManifest.model_validate(
        read_json_object(ProjectLayout(first).index / "manifest.json")
    )
    second_manifest = IndexManifest.model_validate(
        read_json_object(ProjectLayout(second).index / "manifest.json")
    )
    assert first_manifest.project_id != second_manifest.project_id
