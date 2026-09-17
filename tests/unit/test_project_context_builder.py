import hashlib
import os
import subprocess
from pathlib import Path
from uuid import UUID

import pytest

from orqalis.context import ProjectContextBuilder
from orqalis.domain.errors import InputError, PolicyDeniedError
from orqalis.domain.memory import MemoryType
from orqalis.domain.project import Project
from orqalis.git.service import LocalGitService
from orqalis.memory.curated import (
    CuratedMemoryStore,
    MemoryCategory,
    MemoryFreshness,
    MemoryProvenance,
)
from orqalis.memory.service import MemoryService
from orqalis.persistence.filesystem.io import read_json_object
from orqalis.persistence.filesystem.layout import ProjectLayout, bootstrap_project_store
from tests.support.filesystem import filesystem_uow_factory


def _git(path: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid"}
    env.update({"GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid"})
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        env=env,
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def _project(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    root.mkdir()
    _git(root, "init", "-b", "main")
    (root / "sync.py").write_text(
        "import time\n\nclass SyncCoordinator:\n"
        "    def retry_offline(self):\n        return time.time()\n",
        encoding="utf-8",
    )
    (root / "test_sync.py").write_text(
        "from sync import SyncCoordinator\n\n"
        "def test_retry():\n"
        "    SyncCoordinator().retry_offline()\n",
        encoding="utf-8",
    )
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture")
    bootstrap_project_store(root, project_name=name)
    return root


def test_context_combines_ranked_graph_memory_git_and_history(tmp_path: Path) -> None:
    root = _project(tmp_path, "repo")
    memory = CuratedMemoryStore(ProjectLayout(root))
    record = memory.new_record(
        MemoryCategory.PITFALLS,
        "Offline retry durability",
        "Offline retry state must survive process death.",
        MemoryProvenance(type="repository", paths=("sync.py",)),
        verified_commit=_git(root, "rev-parse", "HEAD"),
    )
    memory.save(record)
    tasks = ProjectLayout(root).tasks
    capsule = tasks / "ORQ-20260901-0001"
    (capsule / "final").mkdir(parents=True)
    (capsule / "task.yaml").write_text(
        '{"schema_version":1,"id":"ORQ-20260901-0001",'
        '"run_id":"00000000-0000-0000-0000-000000000001",'
        '"title":"Improve offline retry","status":"COMPLETED",'
        '"created_at":"2026-09-01T00:00:00+00:00",'
        '"completed_at":"2026-09-01T01:00:00+00:00",'
        '"project":{"branch":"feature/retry","starting_commit":"abc"}}',
        encoding="utf-8",
    )
    (capsule / "final" / "summary.md").write_text(
        "Retry state was persisted across restart.", encoding="utf-8"
    )
    active = tasks / "ORQ-20260901-0002"
    active.mkdir()
    (active / "task.yaml").write_text(
        '{"schema_version":1,"id":"ORQ-20260901-0002",'
        '"run_id":"00000000-0000-0000-0000-000000000002",'
        '"title":"Change offline retry behavior","status":"EXECUTING",'
        '"created_at":"2026-09-01T02:00:00+00:00",'
        '"project":{"branch":"feature/current","starting_commit":"abc"}}',
        encoding="utf-8",
    )

    pack = ProjectContextBuilder(root).build("change offline retry behavior", 12_000)
    assert pack.project_name == "repo"
    assert "sync.py" in pack.relevant_files
    assert any(item.node.name == "retry_offline" for item in pack.graph)
    assert [item.record.id for item in pack.memory] == [record.id]
    assert [item.id for item in pack.related_tasks] == ["ORQ-20260901-0001"]
    assert pack.size_chars <= pack.max_chars

    manifest = read_json_object(ProjectLayout(root).manifest)
    identity = manifest["project"]
    assert isinstance(identity, dict)
    project = Project(
        id=UUID(str(identity["id"])),
        name="repo",
        repo_root=root,
        default_branch="main",
    )
    # Existing planner/provider paths keep their stable ContextPack contract,
    # but now receive the ranked local-first graph, memory, and task history.
    unit_of_work = filesystem_uow_factory(root)
    with unit_of_work() as uow:
        uow.projects.add(project)
        uow.commit()
    agent_pack = MemoryService(
        unit_of_work,
        LocalGitService(),
    ).context(project, "change offline retry behavior", 12_000)
    types = {item.item.type for item in agent_pack.items}
    assert {
        MemoryType.KNOWN_ISSUE,
        MemoryType.REPOSITORY_MAP,
        MemoryType.PREVIOUS_RUN,
    } <= types
    assert "sync.py" in agent_pack.relevant_files
    assert agent_pack.size_chars <= 12_000


def test_context_is_root_isolated_and_marks_dirty_files(tmp_path: Path) -> None:
    first = _project(tmp_path, "first")
    second = _project(tmp_path, "second")
    (first / "sync.py").write_text("def changed_retry():\n    return 2\n", encoding="utf-8")
    other_memory = CuratedMemoryStore(ProjectLayout(second))
    other_memory.save(
        other_memory.new_record(
            MemoryCategory.DOMAIN,
            "Second-only knowledge",
            "This must never leak into the first project.",
            MemoryProvenance(type="user"),
        )
    )
    pack = ProjectContextBuilder(first).build("changed retry", 5000)
    assert pack.dirty_paths == ("sync.py",)
    assert all("Second-only" not in item.record.title for item in pack.memory)


def test_context_reads_canonical_store_while_inspecting_linked_worktree(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path, "repo")
    manifest = read_json_object(ProjectLayout(root).manifest)
    identity = manifest["project"]
    assert isinstance(identity, dict)
    project = Project(
        id=UUID(str(identity["id"])),
        name="repo",
        repo_root=root,
        default_branch="main",
    )
    unit_of_work = filesystem_uow_factory(root)
    with unit_of_work() as uow:
        uow.projects.add(project)
        uow.commit()

    source = root / "sync.py"
    memory = CuratedMemoryStore(ProjectLayout(root))
    record = memory.new_record(
        MemoryCategory.PITFALLS,
        "Offline retry durability",
        "Offline retry state must survive process death.",
        MemoryProvenance(
            type="repository",
            paths=("sync.py",),
            content_hashes={"sync.py": hashlib.sha256(source.read_bytes()).hexdigest()},
        ),
        verified_commit=_git(root, "rev-parse", "HEAD"),
    )
    memory.save(record)

    worktree = tmp_path / "feature-worktree"
    _git(root, "worktree", "add", "-b", "feature/context", str(worktree))
    (worktree / "sync.py").write_text(
        "def worktree_retry():\n    return 7\n",
        encoding="utf-8",
    )

    pack = ProjectContextBuilder(root, source_root=worktree).build("worktree offline retry", 12_000)
    assert pack.branch == "feature/context"
    assert pack.dirty_paths == ("sync.py",)
    assert any(item.node.name == "worktree_retry" for item in pack.graph)
    assert [item.freshness for item in pack.memory] == [MemoryFreshness.STALE]
    assert not (worktree / ".orqalis").exists()
    assert (root / ".orqalis" / "memory" / "graph" / "graph.json").is_file()

    agent_pack = MemoryService(unit_of_work, LocalGitService()).context(
        project.model_copy(update={"repo_root": worktree}),
        "worktree offline retry",
        12_000,
    )
    assert "sync.py" in agent_pack.freshness.dirty_paths
    assert any(item.item.title.endswith("worktree_retry") for item in agent_pack.items)
    assert not (worktree / ".orqalis").exists()


def test_context_rejects_an_unrelated_source_repository(tmp_path: Path) -> None:
    root = _project(tmp_path, "first")
    unrelated = _project(tmp_path, "second")
    manifest = read_json_object(ProjectLayout(root).manifest)
    identity = manifest["project"]
    assert isinstance(identity, dict)
    project = Project(
        id=UUID(str(identity["id"])),
        name="first",
        repo_root=root,
        default_branch="main",
    )
    unit_of_work = filesystem_uow_factory(root)
    with unit_of_work() as uow:
        uow.projects.add(project)
        uow.commit()

    with pytest.raises(PolicyDeniedError, match="canonical project repository"):
        ProjectContextBuilder(root, source_root=unrelated)
    with pytest.raises(PolicyDeniedError, match="canonical project repository"):
        MemoryService(unit_of_work, LocalGitService()).context(
            project.model_copy(update={"repo_root": unrelated}),
            "must stay isolated",
        )


def test_context_rejects_a_task_larger_than_the_hard_budget(tmp_path: Path) -> None:
    root = _project(tmp_path, "repo")

    with pytest.raises(InputError, match="exceed the configured budget"):
        ProjectContextBuilder(root).build("x" * 5000, 1000)
