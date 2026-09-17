import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from orqalis.context.service import TaskContextService
from orqalis.domain.errors import NotFoundError, PolicyDeniedError
from orqalis.domain.project import Project
from orqalis.domain.run import Run
from orqalis.memory.curated import CuratedMemoryStore
from orqalis.persistence.filesystem.layout import ProjectLayout
from orqalis.persistence.filesystem.task_store import TaskCapsuleStore


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "Orqalis Tests",
            "GIT_AUTHOR_EMAIL": "tests@example.invalid",
            "GIT_COMMITTER_NAME": "Orqalis Tests",
            "GIT_COMMITTER_EMAIL": "tests@example.invalid",
        },
    )


def task_store(root: Path) -> tuple[TaskCapsuleStore, Run]:
    root.mkdir()
    git(root, "init", "-b", "main")
    (root / "sync.py").write_text(
        "def retry_sync():\n    return 'retry'\n",
        encoding="utf-8",
    )
    git(root, "add", "sync.py")
    git(root, "commit", "-m", "fixture")
    store = TaskCapsuleStore.from_root(root)
    project = Project(name=root.name, repo_root=root, default_branch="main")
    with store.unit_of_work() as uow:
        uow.projects.add(project)
        uow.commit()
    CuratedMemoryStore(ProjectLayout(root)).initialize()
    run = Run(
        project_id=project.id,
        request="Change offline sync retry behavior",
        target_branch="feature/sync",
        base_commit="a" * 40,
    )
    with store.unit_of_work() as uow:
        uow.runs.add(run)
        uow.commit()
    return store, run


def test_context_stage_roundtrips_without_conversation_state(tmp_path: Path) -> None:
    store, run = task_store(tmp_path / "repo")
    first = TaskContextService(store.root, store=store)
    pack = first.create(run.id)

    restarted = TaskContextService(store.root)
    assert restarted.get(run.id) == pack
    assert pack.task == run.request
    assert "sync.py" in pack.relevant_files


def test_context_stage_is_project_isolated(tmp_path: Path) -> None:
    store_a, run_a = task_store(tmp_path / "repo-a")
    store_b, _ = task_store(tmp_path / "repo-b")
    TaskContextService(store_a.root, store=store_a).create(run_a.id)

    with pytest.raises(NotFoundError):
        TaskContextService(store_b.root, store=store_b).get(run_a.id)


def test_context_stage_rejects_secret_bearing_query(tmp_path: Path) -> None:
    store, run = task_store(tmp_path / "repo")
    secret = uuid4().hex
    with pytest.raises(PolicyDeniedError, match="credentials or secrets"):
        TaskContextService(store.root, store=store).create(
            run.id,
            f"Use access_token={secret} to retry sync",
        )
    assert TaskContextService(store.root, store=store).get(run.id) is None
