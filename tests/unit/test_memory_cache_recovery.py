from pathlib import Path
from uuid import uuid4

from orqalis.domain.memory import MemoryItem, MemorySource, ProjectSnapshot, RepositoryFile
from orqalis.persistence.filesystem.layout import bootstrap_project_store
from orqalis.persistence.filesystem.memory_store import FilesystemMemoryRepository


def test_deleted_file_cache_forces_refresh_without_losing_memory(tmp_path: Path) -> None:
    project_id = uuid4()
    layout = bootstrap_project_store(tmp_path, project_id=project_id)
    item = MemoryItem(
        project_id=project_id,
        title="Architecture",
        content="The source tree uses explicit service boundaries.",
        type="architecture",
        source_commit="a" * 40,
    )
    repository = FilesystemMemoryRepository(layout)
    repository.add_item(
        item,
        MemorySource(
            memory_item_id=item.id,
            source_ref="app.py",
            content_hash="b" * 64,
            commit_sha="a" * 40,
        ),
        None,
        None,
    )
    repository.save_file(
        RepositoryFile(
            project_id=project_id,
            path="app.py",
            role="source",
            content_hash="b" * 64,
            last_seen_commit="a" * 40,
        )
    )
    repository.save_snapshot(
        ProjectSnapshot(
            project_id=project_id,
            indexed_commit_sha="a" * 40,
            repo_fingerprint="c" * 64,
            files_scanned=1,
        )
    )
    repository.commit()
    repository.close()

    cache = layout.cache / "search" / "compat-repository-files.jsonl"
    cache.unlink()
    restarted = FilesystemMemoryRepository(layout)

    assert restarted.latest_snapshot(project_id) is None
    assert restarted.files(project_id) == ()
    assert restarted.active_count(project_id) == 1
    restarted.close()
