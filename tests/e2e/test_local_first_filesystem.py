"""Filesystem-only product regression tests; intentionally no PostgreSQL marker."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from uuid import UUID

import pytest

from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.errors import NotFoundError
from orqalis.graph import ProjectGraphEngine
from orqalis.indexing import IndexRecordKind, ProjectIndex
from orqalis.persistence.filesystem import ProjectLayout, TaskCapsuleStore, read_json_object
from orqalis.sdk import Orqalis


def _git(repo: Path, *args: str) -> str:
    environment = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Orqalis Filesystem Test",
        "GIT_AUTHOR_EMAIL": "filesystem-test@orqalis.invalid",
        "GIT_COMMITTER_NAME": "Orqalis Filesystem Test",
        "GIT_COMMITTER_EMAIL": "filesystem-test@orqalis.invalid",
        "GIT_TERMINAL_PROMPT": "0",
    }
    result = subprocess.run(
        [
            "git",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-c",
            "commit.gpgsign=false",
            "-C",
            str(repo),
            *args,
        ],
        env=environment,
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def _repository(parent: Path, name: str, symbol: str) -> Path:
    root = parent / name
    root.mkdir()
    _git(root, "init", "-b", "main")
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (root / "main.py").write_text(
        f"def {symbol}():\n    return '{name}'\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(f"# {name}\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", f"test: create {name}")
    return root


def _goal(symbol: str) -> GoalDraft:
    return GoalDraft(
        goal=f"Preserve {symbol} behavior",
        scope=("main.py",),
        definition_of_done=(f"The {symbol} function remains inspectable",),
        criteria=(
            CriterionDefinition(
                key="AC-source",
                description=f"main.py defines {symbol}",
                validation_spec=FileValidation(path="main.py", contains=symbol),
            ),
        ),
    )


def _initialize_and_prepare(root: Path, symbol: str) -> tuple[UUID, UUID, str]:
    """Use a short-lived SDK instance, returning only durable identifiers."""

    assistant = Orqalis(root=root)
    project = assistant.initialize(root)
    state = assistant.prepare_run(
        project.id,
        f"Inspect {symbol} without external persistence",
        f"feature/{symbol}",
        _goal(symbol),
    )
    capsule_id = TaskCapsuleStore.from_root(root).capsule_id(state.run.id)
    assert capsule_id is not None
    assistant.close()
    return project.id, state.run.id, capsule_id


@pytest.fixture()
def no_database_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "DATABASE_URL",
        "ORQALIS_DATABASE_URL",
        "POSTGRES_HOST",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    ):
        monkeypatch.delenv(name, raising=False)


def test_restart_continuity_and_repository_isolation_without_database(
    tmp_path: Path, no_database_environment: None
) -> None:
    repo_a = _repository(tmp_path, "repo-a", "heliotropeonlya")
    repo_b = _repository(tmp_path, "repo-b", "vermilliononlyb")

    project_a_id, run_a_id, capsule_a = _initialize_and_prepare(repo_a, "heliotropeonlya")
    project_b_id, run_b_id, _ = _initialize_and_prepare(repo_b, "vermilliononlyb")

    manifest_a = read_json_object(ProjectLayout(repo_a).manifest)
    assert manifest_a["storage"] == {"backend": "filesystem"}
    assert str(repo_a.resolve()) not in ProjectLayout(repo_a).manifest.read_text(encoding="utf-8")
    capsule_path = ProjectLayout(repo_a).task(capsule_a)
    assert (capsule_path / "task.yaml").is_file()
    assert (capsule_path / "request.md").is_file()
    assert (capsule_path / "goal" / "acceptance.yaml").is_file()
    assert (capsule_path / "execution" / "events.jsonl").is_file()

    # A new SDK has a new event bus, stores, sessions, and no first-assistant object.
    assistant_a = Orqalis(root=repo_a)
    recovered_projects = assistant_a.list_projects()
    recovered_runs = assistant_a.list_runs()
    assert tuple(project.id for project in recovered_projects) == (project_a_id,)
    assert tuple(run.id for run in recovered_runs) == (run_a_id,)
    before = assistant_a.snapshot(run_a_id)
    resumed = assistant_a.continue_preparation(run_a_id)
    assert resumed.run.id == run_a_id
    assert resumed.last_event_sequence == before.last_event_sequence
    assert TaskCapsuleStore.from_root(repo_a).capsule_id(run_a_id) == capsule_a

    assistant_b = Orqalis(root=repo_b)
    project_a = assistant_a.get_project(project_a_id)
    project_b = assistant_b.get_project(project_b_id)
    assert assistant_a.list_runs(project_b_id) == ()
    assert TaskCapsuleStore.from_root(repo_a).capsule_id(run_b_id) is None
    assert TaskCapsuleStore.from_root(repo_b).capsule_id(run_a_id) is None
    with pytest.raises(NotFoundError, match="Project"):
        assistant_a.get_project(project_b_id)
    with pytest.raises(NotFoundError, match="Run"):
        assistant_a.snapshot(run_b_id)
    with pytest.raises(NotFoundError, match="Project"):
        assistant_a.memory.search(project_b, "vermilliononlyb")
    assert assistant_a.memory.search(project_a, "vermilliononlyb") == ()
    assert assistant_b.memory.search(project_b, "heliotropeonlya") == ()


def test_dirty_graph_refresh_and_rebuildable_cache_and_index(
    tmp_path: Path, no_database_environment: None
) -> None:
    root = _repository(tmp_path, "rebuildable", "initialsymbol")
    project_id, run_id, capsule_id = _initialize_and_prepare(root, "initialsymbol")
    layout = ProjectLayout(root)
    engine = ProjectGraphEngine(root)

    initial = engine.refresh()
    assert initial.metrics.total_files > 0
    assert initial.metrics.processed_files == 0

    (root / "main.py").write_text(
        "def initialsymbol():\n    return 'changed'\n\n"
        "def dirtyfilesymbol():\n    return initialsymbol()\n",
        encoding="utf-8",
    )
    dirty = engine.refresh()
    assert dirty.metrics.processed_files == 1
    assert dirty.metrics.cache_misses == 1
    assert dirty.metrics.changed_paths == ("main.py",)
    assert any(node.name == "dirtyfilesymbol" for node in dirty.graph.nodes)

    first_index = ProjectIndex(root).rebuild()
    assert first_index.metrics.documents_indexed > 0
    assert layout.index.is_dir()
    assert layout.cache.is_dir()
    shutil.rmtree(layout.cache)
    shutil.rmtree(layout.index)

    rebuilt = ProjectIndex(root).rebuild()
    assert rebuilt.metrics.graph_cache_hits == 0
    assert rebuilt.metrics.graph_cache_misses == rebuilt.metrics.file_records
    assert (layout.cache / "parser").is_dir()
    assert (layout.index / "manifest.json").is_file()
    assert ProjectIndex(root).search("dirtyfilesymbol")[0].document.kind in {
        IndexRecordKind.FILE,
        IndexRecordKind.SYMBOL,
    }

    # Derived-data deletion must not remove project identity or Task Capsule history.
    restarted = Orqalis(root=root)
    assert restarted.get_project(project_id).id == project_id
    assert restarted.snapshot(run_id).run.id == run_id
    assert TaskCapsuleStore.from_root(root).capsule_id(run_id) == capsule_id
