"""Release regressions for context categories, model upgrades and branch provenance."""

from collections.abc import Callable
from pathlib import Path
from uuid import uuid5

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from orqalis.core.projects import ProjectService
from orqalis.domain.errors import EmbeddingUnavailableError, InputError
from orqalis.domain.memory import MemoryItem, MemorySource, MemoryType
from orqalis.memory.indexing import DeterministicMemoryIndexer
from orqalis.memory.service import MemoryService
from orqalis.persistence.database import session_factory
from orqalis.persistence.memory_models import MemoryRow
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork
from tests.conftest import fixture_git
from tests.integration.test_memory import ObservedGit

pytestmark = pytest.mark.postgres


def test_context_task_categories_are_source_backed_without_repeated_scans(
    database: Engine, git_repo: Path, commit_all: Callable[[Path], str]
) -> None:
    files = {
        "docs/architecture.md": (
            "# Architecture\nAuthentication boundary separates application layers."
        ),
        "web/Sidebar.tsx": "export const Sidebar = () => null;",
        "data/storage.py": "def storage_transaction(): pass",
        "tests/test_navigation.py": "def test_navigation_keyboard(): pass",
        "docs/domain-rules.md": "# Domain\nInvoices retain their original currency.",
        "docs/known-issues.md": "# Known issues\nOffline refresh currently needs recovery.",
        "docs/adr/0001-storage.md": "# Decision\nStorage uses transactional persistence.",
        "CONTRIBUTING.md": "Git delivery requires reviewed commits.",
    }
    for name, content in files.items():
        source_path = git_repo / name
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(content, encoding="utf-8")
    head = commit_all(git_repo)
    git = ObservedGit()

    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    project = ProjectService(factory, git).initialize(git_repo)
    memory = MemoryService(factory, git)
    memory.refresh(project)
    git.reads.clear()
    git.enumerations = 0
    for query, path, kind in [
        ("architecture authentication", "docs/architecture.md", MemoryType.ARCHITECTURE),
        ("sidebar", "web/Sidebar.tsx", MemoryType.REPOSITORY_MAP),
        ("storage transaction", "data/storage.py", MemoryType.REPOSITORY_MAP),
        ("navigation keyboard testing", "tests/test_navigation.py", MemoryType.REPOSITORY_MAP),
        ("invoices currency domain", "docs/domain-rules.md", MemoryType.DOMAIN),
        ("offline recovery", "docs/known-issues.md", MemoryType.KNOWN_ISSUE),
        ("decision storage", "docs/adr/0001-storage.md", MemoryType.DECISION),
        ("git reviewed commits", "CONTRIBUTING.md", MemoryType.CONVENTION),
    ]:
        context = memory.context(project, query)
        match = next(item for item in context.items if item.item.title == path)
        assert match.item.type == kind
        assert match.sources[0].commit_sha == head
        assert path in context.relevant_files
        assert context.freshness.fresh
    assert not git.reads and not git.enumerations


def test_indexer_and_embedding_upgrade_refresh_once_at_unchanged_head(
    database: Engine, git_repo: Path
) -> None:
    class NextIndexer(DeterministicMemoryIndexer):
        VERSION = "next-fixture"

    class Embeddings:
        dimensions = 3
        model_id = "release-fixture"

        def embed(self, text: str) -> tuple[float, ...]:
            return (1.0, 0.0, 0.0)

    git = ObservedGit()

    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    project = ProjectService(factory, git).initialize(git_repo)
    original = MemoryService(factory, git)
    first = original.refresh(project)
    revised = MemoryService(factory, git, indexer=NextIndexer())
    assert not revised.health(project).fresh
    second = revised.refresh(project)
    assert not second.reused and second.snapshot.id != first.snapshot.id
    assert second.snapshot.indexed_commit_sha == first.snapshot.indexed_commit_sha
    assert revised.refresh(project).reused
    semantic = MemoryService(factory, git, indexer=NextIndexer(), embeddings=Embeddings())
    assert not semantic.health(project).fresh
    assert not semantic.refresh(project).reused
    git.reads.clear()
    matches = semantic.search(project, "semantically equivalent unknown vocabulary")
    assert matches and all(match.score > 0.99 for match in matches)
    assert not git.reads and semantic.health(project).fresh


def test_unmerged_run_memory_is_excluded_until_its_commit_is_in_history(
    database: Engine, git_repo: Path, tmp_path: Path
) -> None:
    (git_repo / "current-policy.md").write_text(
        "Future invoice policy is proposed but not yet implemented.", encoding="utf-8"
    )
    fixture_git(git_repo, "add", "current-policy.md")
    fixture_git(git_repo, "commit", "-m", "test: current source policy")
    git = ObservedGit()
    branch = tmp_path / "feature"
    base = git.resolve_commit(git_repo, "HEAD")
    git.create_worktree(git_repo, branch, "feature/run-memory", base, ("main",))
    (branch / "main.py").write_text("def future_invoice_policy(): pass", encoding="utf-8")
    fixture_git(branch, "add", "main.py")
    fixture_git(branch, "commit", "-m", "test: accepted invoice policy")
    delivered = git.resolve_commit(branch, "HEAD")

    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    project = ProjectService(factory, git).initialize(git_repo)
    memory = MemoryService(factory, git)
    memory.refresh(project)
    item = MemoryItem(
        project_id=project.id,
        type=MemoryType.PREVIOUS_RUN,
        title="Accepted future invoice policy",
        content="Future invoice policy is implemented.",
        source_commit=delivered,
    )
    with factory() as uow:
        uow.memory.add_item(
            item,
            MemorySource(
                memory_item_id=item.id,
                source_type="git_commit",
                source_ref=delivered,
                content_hash=delivered,
                commit_sha=delivered,
            ),
            None,
            None,
        )
        for number in range(35):
            archived = item.model_copy(
                update={
                    "id": uuid5(item.id, str(number)),
                    "title": f"Archived future invoice policy {number}",
                }
            )
            uow.memory.add_item(
                archived,
                MemorySource(
                    memory_item_id=archived.id,
                    source_type="git_commit",
                    source_ref=delivered,
                    content_hash=delivered,
                    commit_sha=delivered,
                ),
                None,
                None,
            )
        uow.commit()
    current_matches = memory.search(project, "future invoice policy", limit=3)
    assert [match.item.title for match in current_matches] == ["current-policy.md"]
    delivered_context = memory.context(
        project.model_copy(update={"repo_root": branch}), "future invoice policy"
    )
    assert any(match.item.type == MemoryType.PREVIOUS_RUN for match in delivered_context.items)
    assert all(
        match.item.type != MemoryType.PREVIOUS_RUN
        for match in memory.search(project, "future invoice policy")
    )
    fixture_git(git_repo, "merge", "--ff-only", "feature/run-memory")
    assert any(
        match.item.type == MemoryType.PREVIOUS_RUN
        for match in memory.search(project, "future invoice policy")
    )
    assert git.status(git_repo).head == delivered
    git.remove_worktree(git_repo, branch)


def test_recovered_embeddings_backfill_stored_content_without_git_reads(
    database: Engine, git_repo: Path
) -> None:
    class RecoveringEmbeddings:
        model_id = "temporarily-offline"
        dimensions = 3
        available = False
        remaining: int | None = None
        calls = 0

        def embed(self, text: str) -> tuple[float, ...]:
            self.calls += 1
            if not self.available or self.remaining == 0:
                raise EmbeddingUnavailableError("unavailable")
            if self.remaining is not None:
                self.remaining -= 1
            return (1.0, 0.0, 0.0)

    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    git, embeddings = ObservedGit(), RecoveringEmbeddings()
    project = ProjectService(factory, git).initialize(git_repo)
    memory = MemoryService(factory, git, embeddings=embeddings)
    first = memory.refresh(project)
    # More than one batch, plus rows that must never be overwritten by this provider.
    protected = {}
    with factory() as uow:
        for index in range(105):
            model = "other-model" if index == 102 else embeddings.model_id
            status = "invalidated" if index == 103 else "active"
            vector = (1.0, 0.0) if index == 104 else None
            item = MemoryItem(
                project_id=project.id,
                type=MemoryType.ARCHITECTURE,
                title=f"Stored fact {index}",
                content=f"Persisted source summary {index}",
                source_commit=first.snapshot.indexed_commit_sha,
                status=status,
            )
            uow.memory.add_item(
                item,
                MemorySource(
                    memory_item_id=item.id,
                    source_ref="main.py",
                    content_hash=str(index),
                    commit_sha=first.snapshot.indexed_commit_sha,
                ),
                vector,
                model,
            )
            if index >= 102:
                protected[index] = item.id
        uow.commit()
    git.reads.clear()
    git.enumerations = 0
    embeddings.calls = 0
    assert memory.refresh(project).reused
    assert embeddings.calls == 1  # A continued outage stops the batch immediately.
    assert memory.search(project, "main.py")  # Structured retrieval remains available.
    embeddings.available = True
    embeddings.remaining = 2
    partial = memory.refresh(project)
    assert partial.reused and partial.snapshot.id == first.snapshot.id
    with Session(database) as session:
        recovered = session.scalars(
            select(MemoryRow).where(
                MemoryRow.project_id == project.id,
                MemoryRow.embedding_model == embeddings.model_id,
                MemoryRow.embedding.is_not(None),
                MemoryRow.id != protected[104],
            )
        ).all()
        assert len(recovered) == 2  # A later outage does not discard completed backfill.
    embeddings.remaining = None
    recovered_refresh = memory.refresh(project)
    assert recovered_refresh.reused and recovered_refresh.snapshot.id == first.snapshot.id
    assert not git.reads and git.enumerations == 0
    with factory() as uow:
        assert not uow.memory.missing_embeddings(project.id, embeddings.model_id)
    with Session(database) as session:
        other_model = session.get(MemoryRow, protected[102])
        invalidated = session.get(MemoryRow, protected[103])
        other_dimensions = session.get(MemoryRow, protected[104])
        assert other_model is not None and other_model.embedding is None
        assert invalidated is not None and invalidated.embedding is None
        assert other_dimensions is not None and other_dimensions.embedding is not None
        assert len(other_dimensions.embedding) == 2
    matches = memory.search(project, "unrelated semantic vocabulary")
    assert matches and all(match.score > 0.99 for match in matches)
    assert protected[104] not in {match.item.id for match in matches}
    embeddings.calls = 0
    assert memory.refresh(project).reused
    assert embeddings.calls == 0  # Completed recovery is idempotent.
    assert not git.reads and git.enumerations == 0


def test_embedding_backfill_validates_provider_dimensions_before_persisting(
    database: Engine, git_repo: Path
) -> None:
    class InvalidRecovery:
        model_id = "invalid-recovery"
        dimensions = 3
        available = False

        def embed(self, text: str) -> tuple[float, ...]:
            if not self.available:
                raise EmbeddingUnavailableError("unavailable")
            return (1.0, 0.0)

    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    git, embeddings = ObservedGit(), InvalidRecovery()
    project = ProjectService(factory, git).initialize(git_repo)
    memory = MemoryService(factory, git, embeddings=embeddings)
    first = memory.refresh(project)
    embeddings.available = True
    git.reads.clear()
    with pytest.raises(InputError, match="invalid vector"):
        memory.refresh(project)
    with Session(database) as session:
        rows = session.scalars(select(MemoryRow).where(MemoryRow.project_id == project.id)).all()
        assert rows and all(row.embedding is None for row in rows)
    assert memory.health(project).indexed_commit == first.snapshot.indexed_commit_sha
    assert not git.reads
