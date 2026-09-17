from pathlib import Path
from uuid import uuid4, uuid5

import pytest

from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.memory import (
    ArchitectureEntity,
    ArchitectureRelation,
    MemoryItem,
    MemorySource,
    MemoryType,
    ProjectSnapshot,
    RepositoryFile,
)
from orqalis.domain.project import Project
from orqalis.persistence.filesystem.io import atomic_write_json
from orqalis.persistence.filesystem.layout import ProjectLayout, bootstrap_project_store
from orqalis.persistence.filesystem.memory_store import FilesystemMemoryRepository


def _repository(tmp_path: Path) -> tuple[Project, FilesystemMemoryRepository]:
    root = tmp_path / "repo"
    root.mkdir()
    project = Project(name="fixture", repo_root=root, default_branch="main")
    layout = bootstrap_project_store(root, project_id=project.id, project_name=project.name)
    atomic_write_json(
        layout.project / "identity.yaml",
        {
            "schema_version": 1,
            **project.model_dump(mode="json", exclude={"repo_root"}),
            "repo_root": ".",
        },
    )
    return project, FilesystemMemoryRepository(ProjectLayout(root))


def test_source_projection_round_trip_and_cache_deletion(tmp_path: Path) -> None:
    project, repository = _repository(tmp_path)
    item = MemoryItem(
        project_id=project.id,
        type=MemoryType.ARCHITECTURE,
        title="Sync module",
        content="The sync module persists retry state.",
        source_commit="a" * 40,
    )
    source = MemorySource(
        memory_item_id=item.id,
        source_ref="src/sync.py",
        content_hash="b" * 64,
        commit_sha="a" * 40,
    )
    repository.add_item(item, source, (1.0, 0.0), "fixture-v1")
    repository.save_snapshot(
        ProjectSnapshot(
            project_id=project.id,
            indexed_commit_sha="a" * 40,
            repo_fingerprint="fingerprint",
            files_scanned=1,
        )
    )
    repository.commit()
    repository.close()

    layout = ProjectLayout(project.repo_root)
    records = tuple((layout.cache / "search" / "source-records").glob("SRC-*.md"))
    assert len(records) == 1
    assert "The sync module" in records[0].read_text(encoding="utf-8")
    assert not tuple((layout.memory / "records").glob("SRC-*.md"))
    (layout.cache / "search" / "embeddings.json").unlink()
    restored = FilesystemMemoryRepository(layout)
    assert restored.search(project.id, ("retry",), 10)[0].item == item
    assert restored.latest_snapshot(project.id).indexed_commit_sha == "a" * 40  # type: ignore[union-attr]


def test_preconsolidation_source_artifacts_are_relocated_out_of_memory(
    tmp_path: Path,
) -> None:
    project, repository = _repository(tmp_path)
    item = MemoryItem(
        project_id=project.id,
        type=MemoryType.ARCHITECTURE,
        title="Legacy derived source",
        content="This source summary is rebuildable.",
        source_commit="a" * 40,
    )
    repository.add_item(
        item,
        MemorySource(
            memory_item_id=item.id,
            source_ref="legacy.py",
            content_hash="b" * 64,
            commit_sha="a" * 40,
        ),
        None,
        None,
    )
    repository.save_snapshot(
        ProjectSnapshot(
            project_id=project.id,
            indexed_commit_sha="a" * 40,
            repo_fingerprint="legacy",
            files_scanned=1,
        )
    )
    repository.commit()
    repository.close()

    layout = ProjectLayout(project.repo_root)
    legacy_records = layout.memory / "records"
    legacy_records.mkdir(parents=True, exist_ok=True)
    cached_record = next((layout.cache / "search" / "source-records").glob("SRC-*.md"))
    cached_record.replace(legacy_records / cached_record.name)
    legacy_history = layout.memory / "history"
    legacy_history.mkdir(parents=True, exist_ok=True)
    (layout.cache / "search" / "source-snapshots.json").replace(legacy_history / "snapshots.json")
    legacy_graph = layout.memory / "graph" / "compatibility-graph.json"
    legacy_graph.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        legacy_graph,
        {"schema_version": 1, "entities": [], "relations": []},
    )

    restored = FilesystemMemoryRepository(layout)

    assert restored.search(project.id, ("rebuildable",), 10)[0].item == item
    assert not tuple(legacy_records.glob("SRC-*.md"))
    assert not (legacy_history / "snapshots.json").exists()
    assert not legacy_graph.exists()
    assert tuple((layout.cache / "search" / "source-records").glob("SRC-*.md"))
    assert (layout.cache / "search" / "source-snapshots.json").is_file()
    assert (layout.cache / "graph" / "legacy-projection.json").is_file()


def test_repository_files_and_graph_are_rebuildable(tmp_path: Path) -> None:
    project, repository = _repository(tmp_path)
    path = "src/service.py"
    file = RepositoryFile(
        id=uuid5(project.id, path),
        project_id=project.id,
        path=path,
        language="Python",
        role="source",
        content_hash="c" * 64,
        last_seen_commit="d" * 40,
    )
    node = ArchitectureEntity(
        id=file.id,
        project_id=project.id,
        name=path,
        source_refs=(path,),
    )
    directory = ArchitectureEntity(
        id=uuid4(),
        project_id=project.id,
        entity_type="directory",
        name="directory:src",
        source_refs=(),
    )
    relation = ArchitectureRelation(
        project_id=project.id,
        source_entity_id=node.id,
        relation_type="belongs_to",
        target_entity_id=directory.id,
        source_refs=(path,),
    )
    repository.save_file(file)
    repository.save_entity(node)
    repository.save_entity(directory)
    repository.save_relation(relation)
    repository.commit()
    assert repository.current_file(project.id, path) == file
    assert len(repository.graph(project.id)) == 2
    repository.remove_file(project.id, path)
    repository.commit()
    entities, relations = repository.graph(project.id)
    assert repository.current_file(project.id, path) is None
    assert all(item.id != node.id for item in entities)
    assert relations == ()


def test_source_memory_rejects_secrets(tmp_path: Path) -> None:
    project, repository = _repository(tmp_path)
    item = MemoryItem(
        project_id=project.id,
        type=MemoryType.CONVENTION,
        title="Unsafe",
        content="access_token=github_pat_private12345678",
        source_commit="e" * 40,
    )
    source = MemorySource(
        memory_item_id=item.id,
        source_ref="README.md",
        content_hash="f" * 64,
        commit_sha="e" * 40,
    )
    with pytest.raises(PolicyDeniedError):
        repository.add_item(item, source, None, None)


def test_concurrent_repository_views_reload_under_lock_without_lost_updates(
    tmp_path: Path,
) -> None:
    project, first = _repository(tmp_path)
    second = FilesystemMemoryRepository(first.layout)

    def record(title: str) -> tuple[MemoryItem, MemorySource]:
        item = MemoryItem(
            project_id=project.id,
            type=MemoryType.ARCHITECTURE,
            title=title,
            content=f"{title} remains durable.",
            source_commit="a" * 40,
        )
        return item, MemorySource(
            memory_item_id=item.id,
            source_ref=f"{title}.py",
            content_hash="b" * 64,
            commit_sha="a" * 40,
        )

    first_item, first_source = record("first")
    second_item, second_source = record("second")
    first.add_item(first_item, first_source, None, None)
    first.commit()
    first.close()
    second.add_item(second_item, second_source, None, None)
    second.commit()
    second.close()

    restored = FilesystemMemoryRepository(ProjectLayout(project.repo_root))
    assert restored.active_count(project.id) == 2
    assert {item.item.title for item in restored.search(project.id, (), 10)} == {
        "first",
        "second",
    }
