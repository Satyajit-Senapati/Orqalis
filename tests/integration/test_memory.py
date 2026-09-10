from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from orqalis.cli.app import app
from orqalis.core.projects import ProjectService
from orqalis.domain.memory import MemoryItem, MemorySource, MemoryType
from orqalis.git.service import LocalGitService
from orqalis.memory.service import MemoryService
from orqalis.persistence.database import session_factory
from orqalis.persistence.memory import SQLMemoryRepository
from orqalis.persistence.memory_models import MemoryRow
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork

pytestmark = pytest.mark.postgres


class ObservedGit(LocalGitService):
    def __init__(self) -> None:
        super().__init__()
        self.enumerations = 0
        self.reads: list[str] = []

    def tracked_files(self, path: Path, commit: str = "HEAD") -> tuple[str, ...]:
        self.enumerations += 1
        return super().tracked_files(path, commit)

    def read_file(self, path: Path, commit: str, relative_path: str) -> bytes:
        self.reads.append(relative_path)
        return super().read_file(path, commit, relative_path)


def test_bootstrap_no_change_incremental_and_delete(
    database: Engine,
    git_repo: Path,
    commit_all: Callable[[Path], str],
) -> None:
    git = ObservedGit()

    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    project = ProjectService(factory, git).initialize(git_repo)
    memory = MemoryService(factory, git)
    first = memory.refresh(project)
    assert len(first.scanned_paths) == 4
    assert memory.health(project).fresh
    git.reads.clear()
    git.enumerations = 0
    unchanged = memory.refresh(project)
    assert unchanged.reused and unchanged.snapshot.id == first.snapshot.id
    assert git.enumerations == 0 and git.reads == []
    (git_repo / "main.py").write_text("def revised_behavior():\n    return 42\n")
    new_commit = commit_all(git_repo)
    second = memory.refresh(project)
    assert second.scanned_paths == ("main.py",)
    assert git.reads == ["main.py"] and git.enumerations == 0
    assert second.invalidated_items == 2  # source fact and project overview
    matches = memory.search(project, "revised_behavior")
    assert matches[0].sources[0].commit_sha == new_commit
    with Session(database) as session:
        old = session.scalars(
            select(MemoryRow).where(
                MemoryRow.project_id == project.id,
                MemoryRow.title == "main.py",
                MemoryRow.status == "superseded",
            )
        ).one()
        assert old.superseded_by == matches[0].item.id
    (git_repo / "main.py").unlink()
    commit_all(git_repo)
    memory.refresh(project)
    assert not memory.search(project, "revised_behavior")
    entities, relations = memory.graph(project)
    assert "main.py" not in {entity.name for entity in entities}
    assert relations
    assert all(
        relation.source_entity_id in {entity.id for entity in entities} for relation in relations
    )


def test_context_dirty_overlay_budget_and_secrets(
    database: Engine,
    git_repo: Path,
    commit_all: Callable[[Path], str],
) -> None:
    (git_repo / "architecture.md").write_text(
        "# Authentication architecture\nValidation lives in auth.py.\napi_key=secret-value\n"
    )
    (git_repo / ".env").write_text("PRIVATE_TOKEN=must-not-persist")
    (git_repo / "private.md").write_text("<thinking>private scratch</thinking>")
    commit_all(git_repo)
    git = LocalGitService()

    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    project = ProjectService(factory, git).initialize(git_repo)
    memory = MemoryService(factory, git)
    memory.refresh(project)
    pack = memory.context(project, "authentication architecture", max_chars=2000)
    assert "architecture.md" in pack.relevant_files
    assert pack.size_chars <= 2000
    assert pack.freshness.fresh
    assert "secret-value" not in pack.model_dump_json()
    with Session(database) as session:
        text = str(
            session.scalars(
                select(MemoryRow.content).where(MemoryRow.project_id == project.id)
            ).all()
        )
        assert "must-not-persist" not in text and "private scratch" not in text
    (git_repo / "architecture.md").write_text("new uncommitted design")
    dirty = memory.context(project, "authentication")
    assert not dirty.freshness.fresh
    assert dirty.requires_inspection
    assert dirty.targeted_inspection_paths == ("architecture.md",)
    assert "new uncommitted design" not in dirty.model_dump_json()
    assert memory.context(project, "nonexistent concept").requires_inspection


def test_vector_search_is_project_and_model_scoped(database: Engine, git_repo: Path) -> None:
    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    project = ProjectService(factory, LocalGitService()).initialize(git_repo)
    with Session(database) as session, session.begin():
        repository = SQLMemoryRepository(session)
        for title, vector, model in [
            ("matching", (1.0, 0.0, 0.0), "fixture-v1"),
            ("unrelated", (0.0, 1.0, 0.0), "fixture-v1"),
            ("other-model", (1.0, 0.0, 0.0), "fixture-v2"),
        ]:
            item = MemoryItem(
                project_id=project.id,
                type=MemoryType.ARCHITECTURE,
                title=title,
                content=title,
                source_commit="fixture",
            )
            source = MemorySource(
                memory_item_id=item.id,
                source_ref="main.py",
                content_hash="hash",
                commit_sha="fixture",
            )
            repository.add_item(item, source, vector, model)
        results = repository.search(
            project.id, ("no-text-match",), 10, (1.0, 0.0, 0.0), "fixture-v1"
        )
        assert results[0].item.title == "matching"
        assert {result.item.title for result in results} == {"matching", "unrelated"}


def test_memory_cli(database: Engine, git_repo: Path) -> None:
    import json

    runner = CliRunner()
    for args in [
        ["init"],
        ["memory", "status"],
        ["memory", "search", "main"],
        ["memory", "refresh"],
        ["context", "main"],
    ]:
        result = runner.invoke(app, [*args, "--repo", str(git_repo), "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) is not None


def test_failed_refresh_rolls_back_and_retries(
    database: Engine,
    git_repo: Path,
    commit_all: Callable[[Path], str],
) -> None:
    from orqalis.git.service import GitError

    class FailingGit(ObservedGit):
        failing = False

        def read_file(self, path: Path, commit: str, relative_path: str) -> bytes:
            if self.failing and relative_path == "main.py":
                raise GitError("injected failure")
            return super().read_file(path, commit, relative_path)

    git = FailingGit()

    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    project = ProjectService(factory, git).initialize(git_repo)
    memory = MemoryService(factory, git)
    baseline = memory.refresh(project)
    (git_repo / "AGENTS.md").write_text("new policy")
    (git_repo / "main.py").write_text("def changed(): pass")
    commit_all(git_repo)
    git.failing = True
    with pytest.raises(GitError):
        memory.refresh(project)
    with factory() as uow:
        assert uow.memory.latest_snapshot(project.id) == baseline.snapshot
        assert not uow.memory.search(project.id, ("new policy",), 10)
    git.failing = False
    assert (
        memory.refresh(project).snapshot.indexed_commit_sha != baseline.snapshot.indexed_commit_sha
    )


def test_concurrent_refresh_has_one_atomic_snapshot(database: Engine, git_repo: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    project = ProjectService(factory, LocalGitService()).initialize(git_repo)
    memory = MemoryService(factory, LocalGitService())
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: memory.refresh(project), range(2)))
    assert results[0].snapshot.id == results[1].snapshot.id
    assert sum(result.reused for result in results) == 1


def test_unavailable_embeddings_fall_back_to_structured_search(
    database: Engine,
    git_repo: Path,
) -> None:
    from orqalis.domain.errors import EmbeddingUnavailableError

    class OfflineEmbeddings:
        model_id = "offline"
        dimensions = 3

        def embed(self, text: str) -> tuple[float, ...]:
            raise EmbeddingUnavailableError("unavailable")

    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    project = ProjectService(factory, LocalGitService()).initialize(git_repo)
    memory = MemoryService(factory, LocalGitService(), embeddings=OfflineEmbeddings())
    assert memory.search(project, "main")


def test_large_repository_refresh_reads_only_changed_source(
    database: Engine,
    git_repo: Path,
    commit_all: Callable[[Path], str],
    record_testsuite_property: Callable[[str, object], None],
) -> None:
    import time

    source = git_repo / "packages"
    source.mkdir()
    for index in range(500):
        (source / f"module_{index}.py").write_text(f"def feature_{index}(): return {index}\n")
    commit_all(git_repo)
    git = ObservedGit()

    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    project = ProjectService(factory, git).initialize(git_repo)
    memory = MemoryService(factory, git)
    started = time.monotonic()
    initial = memory.refresh(project)
    record_testsuite_property("bootstrap_seconds", time.monotonic() - started)
    assert len(initial.scanned_paths) == 504
    git.reads.clear()
    started = time.monotonic()
    assert memory.refresh(project).reused
    record_testsuite_property("unchanged_seconds", time.monotonic() - started)
    assert not git.reads
    (source / "module_250.py").write_text("def feature_250(): return 'updated'\n")
    commit_all(git_repo)
    started = time.monotonic()
    refreshed = memory.refresh(project)
    record_testsuite_property("incremental_seconds", time.monotonic() - started)
    assert refreshed.scanned_paths == ("packages/module_250.py",)
    assert git.reads == ["packages/module_250.py"]
    assert memory.health(project).active_items == 505
