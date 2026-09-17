from pathlib import Path
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from orqalis.cli.app import app
from orqalis.config.settings import Settings
from orqalis.domain.errors import NotFoundError, PolicyDeniedError
from orqalis.domain.project import Project
from orqalis.persistence.filesystem import (
    ProjectLayout,
    UnsupportedSchemaError,
    atomic_write_bytes,
    atomic_write_json,
    load_manifest,
    read_json_object,
)
from orqalis.sdk import Orqalis
from tests.conftest import fixture_git


def _persist_project(sdk: Orqalis, root: Path, name: str) -> Project:
    project = Project(
        id=uuid4(),
        name=name,
        repo_root=root,
        default_branch="main",
    )
    with sdk.unit_of_work() as uow:
        uow.projects.add(project)
        uow.commit()
    return project


def test_default_sdk_starts_without_database_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setenv("ORQALIS_PROJECT_ROOT", str(root))
    # A stale legacy variable is irrelevant to the standard filesystem runtime.
    monkeypatch.setenv("ORQALIS_DATABASE_URL", "not-a-database-url")

    sdk = Orqalis()
    try:
        assert sdk.project_root == root.resolve()
        assert sdk.contexts is None
        assert sdk.list_projects() == ()
        assert not hasattr(sdk, "engine")
    finally:
        sdk.close()


def test_explicit_root_wins_and_project_stores_are_isolated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root_a = tmp_path / "repo-a"
    root_b = tmp_path / "repo-b"
    root_a.mkdir()
    root_b.mkdir()
    monkeypatch.setenv("ORQALIS_PROJECT_ROOT", str(root_b))

    sdk_a = Orqalis(root=root_a)
    sdk_b = Orqalis()
    try:
        project_a = _persist_project(sdk_a, root_a, "Project A")
        project_b = _persist_project(sdk_b, root_b, "Project B")

        assert sdk_a.list_projects() == (project_a,)
        assert sdk_b.list_projects() == (project_b,)
        with pytest.raises(NotFoundError):
            sdk_a.get_project(project_b.id)
        with pytest.raises(NotFoundError):
            sdk_b.get_project(project_a.id)
        with pytest.raises(PolicyDeniedError, match="root"):
            sdk_a.initialize(root_b)
    finally:
        sdk_a.close()
        sdk_b.close()


def test_injected_unit_of_work_remains_supported_without_root_resolution(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    owner = Orqalis(root=root)
    try:
        project = _persist_project(owner, root, "Injected")
        injected = Orqalis(settings=Settings(), unit_of_work=owner.unit_of_work)
        try:
            assert injected.project_root is None
            assert injected.contexts is None
            assert injected.get_project(project.id) == project
        finally:
            injected.close()
    finally:
        owner.close()


def _schema_one_manifest(project_id: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "project": {"id": project_id, "name": "Legacy project"},
        "initialized_at": "2026-09-16T14:20:00+05:30",
        "graph": {"indexed_commit": "abc123", "indexed_branch": "main"},
    }


def test_sdk_open_migrates_schema_one_and_preserves_project_data(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    layout = ProjectLayout(root)
    layout.store.mkdir()
    project_id = str(uuid4())
    old_manifest = _schema_one_manifest(project_id)
    atomic_write_json(layout.manifest, old_manifest)
    original_manifest = layout.manifest.read_bytes()
    durable = b"# Durable product memory\n\nKeep this content.\n"
    atomic_write_bytes(layout.memory / "product.md", durable)

    sdk = Orqalis(root=root)
    try:
        assert sdk.list_projects() == ()
    finally:
        sdk.close()

    assert load_manifest(layout)["schema_version"] == 2
    assert (layout.memory / "product.md").read_bytes() == durable
    backups = tuple((layout.store / "backups").glob("manifest.schema-1.*.yaml"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == original_manifest


def test_sdk_open_fails_closed_for_unsupported_future_schema(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    layout = ProjectLayout(root)
    layout.store.mkdir()
    future = {**_schema_one_manifest(str(uuid4())), "schema_version": 99}
    atomic_write_json(layout.manifest, future)
    original_manifest = layout.manifest.read_bytes()

    with pytest.raises(UnsupportedSchemaError, match="99"):
        Orqalis(root=root)

    assert layout.manifest.read_bytes() == original_manifest
    assert not (layout.store / "backups").exists()
    assert not layout.runtime.exists()
    assert read_json_object(layout.manifest)["schema_version"] == 99


def test_status_command_migrates_schema_one_through_root_bound_sdk(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    fixture_git(root, "init", "-b", "main")
    (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
    fixture_git(root, "add", "README.md")
    fixture_git(root, "commit", "-m", "initial")

    project = Project(
        id=uuid4(),
        name="Legacy project",
        repo_root=root,
        default_branch="main",
    )
    layout = ProjectLayout(root)
    layout.store.mkdir()
    identity = project.model_dump(mode="json", exclude={"repo_root"})
    identity["repo_root"] = "."
    atomic_write_json(layout.project / "identity.yaml", {"schema_version": 1, **identity})
    atomic_write_json(layout.manifest, _schema_one_manifest(str(project.id)))

    result = CliRunner().invoke(app, ["status", "--repo", str(root), "--json"])

    assert result.exit_code == 0, result.output
    assert load_manifest(layout)["schema_version"] == 2
    assert read_json_object(layout.project / "identity.yaml")["id"] == str(project.id)
