from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.domain.errors import InputError, PolicyDeniedError
from orqalis.domain.memory import ArchitectureEntity, ArchitectureRelation, ContextPack
from orqalis.domain.project import Project
from orqalis.git.contracts import GitStatus
from orqalis.git.service import GitError, LocalGitService
from orqalis.memory.curated import CuratedMemoryStore, MemoryCategory, MemoryProvenance
from orqalis.memory.service import MemoryService
from orqalis.persistence.filesystem import ProjectLayout
from orqalis.sdk import Orqalis
from tests.conftest import fixture_git


def test_project_brain_projects_authoritative_context_not_legacy_cache(git_repo: Path) -> None:
    sdk = Orqalis(root=git_repo)
    try:
        project = sdk.initialize(git_repo)
        store = CuratedMemoryStore(ProjectLayout(git_repo))
        record = store.new_record(
            MemoryCategory.DOMAIN,
            "Repository authority",
            "Durable project knowledge is owned by the curated filesystem store.",
            MemoryProvenance(type="user"),
        )
        proposal = store.propose(record, "Keep the persistence authority explicit")
        assert store.approve(proposal.id, "Verified by the repository maintainer").status == (
            "APPROVED"
        )

        source_records = tuple(
            (git_repo / ".orqalis" / "cache" / "search" / "source-records").glob("SRC-*.md")
        )
        assert source_records

        brain = sdk.brain.get(project.id)

        assert brain.query == ""
        assert any(match.item.title == record.title for match in brain.matches)
        assert not {
            "AGENTS.md",
            "main.py",
            "Project overview",
            "pyproject.toml",
            "tests/test_main.py",
        }.intersection(match.item.title for match in brain.matches)
        assert brain.freshness.active_items == len(brain.matches)
        assert brain.entities
    finally:
        sdk.close()


class _BrainRecordingGit(LocalGitService):
    def __init__(self) -> None:
        super().__init__()
        self.status_roots: list[Path] = []

    def status(self, path: Path) -> GitStatus:
        self.status_roots.append(path)
        return super().status(path)


def _brain_context_shape(pack: ContextPack) -> tuple[object, ...]:
    return (
        pack.project_id,
        pack.task,
        pack.relevant_files,
        pack.freshness,
        pack.confidence,
        pack.targeted_inspection_paths,
        pack.requires_inspection,
        pack.size_chars,
        tuple(
            (
                m.item.id,
                m.item.title,
                m.item.content,
                m.item.status,
                m.item.source_commit,
                m.score,
                tuple((s.id, s.source_ref, s.content_hash, s.commit_sha) for s in m.sources),
            )
            for m in pack.items
        ),
    )


def test_brain_same_root_shares_one_fresh_graph_with_context(git_repo: Path) -> None:
    sdk = Orqalis(root=git_repo)
    try:
        project = sdk.initialize(git_repo)
        git = _BrainRecordingGit()
        sdk.memory.git = git
        query = "main project testing"
        expected_entities, expected_relations = sdk.memory.graph(project)
        expected_context = sdk.memory.context(project, query)
        git.status_roots.clear()
        entities, relations, context = sdk.memory.graph_context(project, project, query)
        assert git.status_roots == [git_repo]
        assert [v.model_dump(exclude={"created_at"}) for v in entities] == [
            v.model_dump(exclude={"created_at"}) for v in expected_entities
        ]
        assert [v.model_dump(exclude={"created_at"}) for v in relations] == [
            v.model_dump(exclude={"created_at"}) for v in expected_relations
        ]
        assert _brain_context_shape(context) == _brain_context_shape(expected_context)
        git.status_roots.clear()
        brain = sdk.brain.get(project.id, query)
        assert git.status_roots == [git_repo]
        assert brain.freshness == context.freshness
        assert brain.entities and brain.matches
        (git_repo / "main.py").write_text(
            "def fresh_brain_symbol():\n    return 8\n", encoding="utf-8"
        )
        git.status_roots.clear()
        changed = sdk.brain.get(project.id, "fresh_brain_symbol")
        assert git.status_roots == [git_repo]
        assert "main.py" in changed.freshness.dirty_paths
        assert any(v.name == "fresh_brain_symbol" for v in changed.entities)
        fixture_git(git_repo, "add", "main.py")
        fixture_git(git_repo, "commit", "-m", "Brain freshness fixture")
        git.status_roots.clear()
        committed = sdk.brain.get(project.id, "fresh_brain_symbol")
        assert git.status_roots == [git_repo]
        assert committed.freshness.current_commit != brain.freshness.current_commit
        assert "main.py" not in committed.freshness.dirty_paths
    finally:
        sdk.close()


def test_brain_graph_context_keeps_canonical_and_worktree_views_separate(
    git_repo: Path, tmp_path: Path
) -> None:
    sdk = Orqalis(root=git_repo)
    try:
        project = sdk.initialize(git_repo)
        worktree = tmp_path / "brain-worktree"
        fixture_git(git_repo, "worktree", "add", "-b", "brain-worktree", str(worktree))
        (worktree / "main.py").write_text(
            "def worktree_brain_symbol():\n    return 9\n", encoding="utf-8"
        )
        fixture_git(worktree, "add", "main.py")
        fixture_git(worktree, "commit", "-m", "Worktree Brain fixture")
        (worktree / "main.py").write_text(
            "def dirty_worktree_brain():\n    return 10\n", encoding="utf-8"
        )
        git = _BrainRecordingGit()
        sdk.memory.git = git
        entities, _, context = sdk.memory.graph_context(
            project, project.model_copy(update={"repo_root": worktree}), "dirty_worktree_brain"
        )
        assert git.status_roots == [git_repo, worktree]
        assert not any(v.name == "dirty_worktree_brain" for v in entities)
        assert any(m.item.title.endswith("dirty_worktree_brain") for m in context.items)
        assert "main.py" in context.freshness.dirty_paths
        assert context.freshness.current_commit == fixture_git(worktree, "rev-parse", "HEAD")
        assert not (worktree / ".orqalis").exists()
    finally:
        sdk.close()


@pytest.mark.parametrize("override", ["graph", "context", "subclass"])
def test_brain_custom_memory_dispatch_remains_live(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, override: str
) -> None:
    sdk = Orqalis(root=git_repo)
    try:
        project = sdk.initialize(git_repo)
        calls: list[str] = []
        git = _BrainRecordingGit()
        memory = sdk.memory
        memory.git = git
        if override == "subclass":

            class CustomMemory(MemoryService):
                def graph(
                    self, project: Project
                ) -> tuple[tuple[ArchitectureEntity, ...], tuple[ArchitectureRelation, ...]]:
                    calls.append("graph")
                    return super().graph(project)

            memory = CustomMemory(sdk.unit_of_work, git)
            sdk.brain.memory = memory
        elif override == "graph":
            original_graph = memory.graph

            def graph(
                project: Project,
            ) -> tuple[tuple[ArchitectureEntity, ...], tuple[ArchitectureRelation, ...]]:
                calls.append("graph")
                return original_graph(project)

            monkeypatch.setattr(memory, "graph", graph)
        else:
            original_context = memory.context

            def context(project: Project, task: str, max_chars: int = 20_000) -> ContextPack:
                calls.append("context")
                return original_context(project, task, max_chars)

            monkeypatch.setattr(memory, "context", context)
        sdk.brain.get(project.id, "main testing")
        assert calls == ["context" if override == "context" else "graph"]
        assert git.status_roots == [git_repo, git_repo]
    finally:
        sdk.close()


@pytest.mark.parametrize("canonical_state", ["missing", "changed"])
def test_brain_fresh_canonical_lookup_preserves_original_fallback(
    git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, canonical_state: str
) -> None:
    sdk = Orqalis(root=git_repo)
    try:
        project = sdk.initialize(git_repo)
        canonical = (
            None
            if canonical_state == "missing"
            else project.model_copy(update={"repo_root": tmp_path / "changed"})
        )

        @contextmanager
        def lookup() -> Iterator[ProjectUnitOfWork]:
            yield cast(
                ProjectUnitOfWork,
                SimpleNamespace(projects=SimpleNamespace(get=lambda _: canonical)),
            )

        memory = MemoryService(cast(Callable[[], ProjectUnitOfWork], lookup), sdk.git)
        graph = Mock(return_value=((), ()))
        context = Mock(side_effect=PolicyDeniedError("fallback context guarded"))
        # Class spies observe fallback without registering an instance override.
        monkeypatch.setattr(MemoryService, "graph", graph)
        monkeypatch.setattr(MemoryService, "context", context)
        with pytest.raises(PolicyDeniedError, match="fallback context guarded"):
            memory.graph_context(project, project, "main testing")
        graph.assert_called_once_with(project)
        context.assert_called_once_with(project, "main testing", 20_000)
    finally:
        sdk.close()


def test_brain_combination_rejects_unrelated_repository(git_repo: Path, tmp_path: Path) -> None:
    sdk = Orqalis(root=git_repo)
    try:
        project = sdk.initialize(git_repo)
        other = tmp_path / "unrelated-brain"
        other.mkdir()
        fixture_git(other, "init", "-b", "main")
        (other / "other.py").write_text("x = 1\n", encoding="utf-8")
        fixture_git(other, "add", "other.py")
        fixture_git(other, "commit", "-m", "Unrelated Brain fixture")
        with pytest.raises(PolicyDeniedError, match="canonical project repository"):
            sdk.memory.graph_context(
                project, project.model_copy(update={"repo_root": other}), "main"
            )
    finally:
        sdk.close()


@pytest.mark.parametrize(
    "task,budget", [("", 20_000), ("x" * 10001, 20_000), ("main", 999), ("main", 200001)]
)
def test_brain_combined_context_keeps_query_and_budget_guards(
    git_repo: Path, task: str, budget: int
) -> None:
    sdk = Orqalis(root=git_repo)
    try:
        project = sdk.initialize(git_repo)
        with pytest.raises(InputError):
            sdk.memory.graph_context(project, project, task, budget)
    finally:
        sdk.close()


def test_brain_combined_refresh_uses_injected_git_denial(git_repo: Path) -> None:
    class DeniedGit(LocalGitService):
        def status(self, path: Path) -> GitStatus:
            raise GitError("injected status denied")

    sdk = Orqalis(root=git_repo)
    try:
        project = sdk.initialize(git_repo)
        sdk.memory.git = DeniedGit()
        with pytest.raises(GitError, match="injected status denied"):
            sdk.memory.graph_context(project, project, "main testing")
    finally:
        sdk.close()


def test_brain_combined_build_keeps_manifest_validation(git_repo: Path) -> None:
    from orqalis.persistence.filesystem.layout import ManifestValidationError

    sdk = Orqalis(root=git_repo)
    try:
        project = sdk.initialize(git_repo)
        manifest = ProjectLayout(git_repo).manifest
        original = manifest.read_bytes()
        try:
            manifest.write_bytes(b'{"project":')
            with pytest.raises(ManifestValidationError):
                sdk.memory.graph_context(project, project, "main testing")
        finally:
            manifest.write_bytes(original)
    finally:
        sdk.close()
