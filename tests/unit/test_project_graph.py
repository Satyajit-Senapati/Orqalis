import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from orqalis.domain.errors import PolicyDeniedError
from orqalis.git.service import LocalGitService
from orqalis.graph import (
    GraphEdge,
    GraphNode,
    GraphNodeKind,
    GraphProvenance,
    GraphRelation,
    ProjectGraph,
    ProjectGraphEngine,
)
from orqalis.memory.curated import (
    CuratedMemoryStore,
    DurableMemoryRecord,
    MemoryCategory,
    MemoryFreshness,
    MemoryProvenance,
    source_hashes,
)
from orqalis.persistence.filesystem import bootstrap_project_store
from orqalis.persistence.filesystem.io import (
    FilesystemFormatError,
    read_json_object_with_sha256,
)
from orqalis.persistence.filesystem.layout import ProjectLayout, load_manifest


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, message: str = "test: graph fixture") -> str:
    _git(repo, "add", ".")
    _git(
        repo,
        "-c",
        "user.name=Orqalis Test",
        "-c",
        "user.email=test@orqalis.invalid",
        "commit",
        "-m",
        message,
    )
    return _git(repo, "rev-parse", "HEAD")


def _add_graph_fixture(repo: Path) -> None:
    package = repo / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("from .service import Service\n", encoding="utf-8")
    (package / "base.py").write_text("class Base:\n    pass\n", encoding="utf-8")
    (package / "helpers.py").write_text(
        "def helper():\n    return 1\n",
        encoding="utf-8",
    )
    (package / "service.py").write_text(
        "from pkg.base import Base\n"
        "from pkg.helpers import helper\n\n"
        "class Service(Base):\n"
        "    def run(self):\n"
        "        return helper()\n\n"
        "def make_service():\n"
        "    return Service()\n",
        encoding="utf-8",
    )
    (repo / "docs").mkdir()
    (repo / "docs" / "architecture.md").write_text("# Architecture\n", encoding="utf-8")
    (repo / "config.yaml").write_text("enabled: true\n", encoding="utf-8")
    (repo / "tests" / "test_service.py").write_text(
        "from pkg.service import Service\n\ndef test_service():\n    assert Service().run() == 1\n",
        encoding="utf-8",
    )
    _commit(repo)


def test_graph_models_support_typed_and_extension_relations() -> None:
    node = GraphNode(id="file:one", kind=GraphNodeKind.FILE, name="one.py")
    extracted = GraphEdge(
        id="edge:one",
        source_id=node.id,
        target_id="module:one",
        relation=GraphRelation.DEFINES,
        provenance=GraphProvenance.EXTRACTED,
        confidence=1,
        evidence=("one.py:1",),
    )
    extension = extracted.model_copy(
        update={"id": "edge:custom", "relation": "GENERATES", "confidence": 0.6}
    )

    assert extracted.relation == GraphRelation.DEFINES
    assert extension.relation == "GENERATES"
    assert extension.provenance == GraphProvenance.EXTRACTED
    with pytest.raises(ValidationError):
        GraphEdge(
            id="edge:invalid",
            source_id="a",
            target_id="b",
            relation=GraphRelation.CALLS,
            provenance=GraphProvenance.INFERRED,
            confidence=1.1,
        )


def test_python_ast_graph_and_persisted_manifest(git_repo: Path) -> None:
    _add_graph_fixture(git_repo)
    bootstrap_project_store(git_repo)
    result = ProjectGraphEngine(git_repo).refresh()

    kinds = {str(node.kind) for node in result.graph.nodes}
    relations = {str(edge.relation) for edge in result.graph.edges}
    assert {
        "FILE",
        "MODULE",
        "CLASS",
        "FUNCTION",
        "METHOD",
        "TEST",
        "CONFIGURATION",
        "DOCUMENTATION",
    } <= kinds
    assert {"DEFINES", "IMPORTS", "CALLS", "EXTENDS", "TESTS"} <= relations
    assert any(
        edge.relation == GraphRelation.TESTS and edge.provenance == GraphProvenance.INFERRED
        for edge in result.graph.edges
    )
    assert all(
        edge.provenance == GraphProvenance.EXTRACTED
        for edge in result.graph.edges
        if edge.relation == GraphRelation.IMPORTS
    )
    service = next(
        node
        for node in result.graph.nodes
        if node.name == "Service" and node.kind == GraphNodeKind.CLASS
    )
    assert service.file_path == "pkg/service.py"
    assert service.line_start == 4
    assert service.source_hash == result.manifest.file_hashes["pkg/service.py"]
    package_module = next(
        node
        for node in result.graph.nodes
        if node.kind == GraphNodeKind.MODULE and node.name == "pkg"
    )
    service_module = next(
        node
        for node in result.graph.nodes
        if node.kind == GraphNodeKind.MODULE and node.name == "pkg.service"
    )
    assert any(
        edge.source_id == package_module.id
        and edge.target_id == service_module.id
        and edge.relation == GraphRelation.IMPORTS
        for edge in result.graph.edges
    )

    graph_path = git_repo / ".orqalis" / "memory" / "graph" / "graph.json"
    manifest_path = graph_path.with_name("manifest.json")
    assert graph_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["parser_version"]
    assert manifest["indexed_branch"] == "main"
    assert manifest["indexed_head"] == _git(git_repo, "rev-parse", "HEAD")
    assert manifest["indexed_commit"] == manifest["indexed_head"]
    assert len(manifest["graph_sha256"]) == 64
    assert "last_indexed_at" in manifest
    assert str(git_repo) not in manifest_path.read_text(encoding="utf-8")
    assert result.metrics.processed_files == result.metrics.total_files
    assert result.metrics.cache_misses == result.metrics.total_files


def test_dirty_incremental_refresh_cache_hit_rename_and_delete(git_repo: Path) -> None:
    bootstrap_project_store(git_repo)
    engine = ProjectGraphEngine(git_repo)
    initial = engine.refresh()
    unchanged = engine.refresh()
    assert unchanged.metrics.processed_files == 0
    assert unchanged.metrics.cache_hits == 0

    (git_repo / "main.py").write_text(
        "answer = 43\n\ndef fresh():\n    return answer\n",
        encoding="utf-8",
    )
    dirty = engine.refresh()
    assert dirty.metrics.processed_files == 1
    assert dirty.metrics.cache_misses == 1
    assert dirty.metrics.changed_paths == ("main.py",)
    assert any(node.name == "fresh" for node in dirty.graph.nodes)

    _git(git_repo, "mv", "main.py", "renamed.py")
    renamed = engine.refresh()
    assert renamed.metrics.processed_files == 1
    assert renamed.metrics.deleted_files == 1
    assert renamed.metrics.cache_hits >= 1
    assert not any(node.file_path == "main.py" for node in renamed.graph.nodes)
    assert any(node.file_path == "renamed.py" for node in renamed.graph.nodes)

    (git_repo / "renamed.py").unlink()
    deleted = engine.refresh()
    assert deleted.metrics.deleted_files == 1
    assert not any(node.file_path == "renamed.py" for node in deleted.graph.nodes)
    assert deleted.manifest.indexed_commit == initial.manifest.indexed_commit


def test_schema_valid_graph_tampering_forces_deterministic_rebuild(git_repo: Path) -> None:
    bootstrap_project_store(git_repo)
    engine = ProjectGraphEngine(git_repo)
    initial = engine.refresh()
    graph_path = git_repo / ".orqalis" / "memory" / "graph" / "graph.json"
    document = json.loads(graph_path.read_text(encoding="utf-8"))
    document["nodes"].append(
        {
            "id": "injected",
            "kind": "REFERENCE",
            "name": "INJECTED",
            "file_path": None,
            "line_start": None,
            "line_end": None,
            "language": None,
            "metadata": {},
            "source_hash": None,
        }
    )
    graph_path.write_text(json.dumps(document), encoding="utf-8")

    rebuilt = engine.refresh()

    assert not any(node.id == "injected" for node in rebuilt.graph.nodes)
    assert rebuilt.metrics.processed_files == initial.metrics.total_files


def test_graph_refresh_synchronizes_top_level_manifest_cursor(git_repo: Path) -> None:
    bootstrap_project_store(git_repo)
    engine = ProjectGraphEngine(git_repo)
    engine.refresh()
    (git_repo / "second.py").write_text("VALUE = 2\n", encoding="utf-8")
    _commit(git_repo)

    refreshed = engine.refresh()
    top_graph = load_manifest(ProjectLayout(git_repo))["graph"]

    assert isinstance(top_graph, dict)
    assert top_graph["indexed_commit"] == refreshed.manifest.indexed_commit
    assert top_graph["indexed_branch"] == refreshed.manifest.indexed_branch


def test_untracked_files_and_full_rebuild_after_cache_deletion(git_repo: Path) -> None:
    bootstrap_project_store(git_repo)
    engine = ProjectGraphEngine(git_repo)
    engine.refresh()
    (git_repo / "new_module.py").write_text(
        "def untracked_symbol():\n    return 1\n",
        encoding="utf-8",
    )

    incremental = engine.refresh()
    assert incremental.metrics.processed_files == 1
    assert "new_module.py" in incremental.manifest.file_hashes
    assert any(node.name == "untracked_symbol" for node in incremental.graph.nodes)

    parser_cache = git_repo / ".orqalis" / "cache" / "parser"
    shutil.rmtree(parser_cache)
    rebuilt = engine.rebuild()
    assert rebuilt.metrics.processed_files == rebuilt.metrics.total_files
    assert rebuilt.metrics.cache_hits == 0
    assert rebuilt.metrics.cache_misses == rebuilt.metrics.total_files
    assert parser_cache.is_dir()


def test_graph_engine_isolates_repository_roots(git_repo: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-b", "main")
    (other / "only_other.py").write_text("def other():\n    return 2\n", encoding="utf-8")
    _commit(other)
    bootstrap_project_store(git_repo)
    bootstrap_project_store(other)

    first = ProjectGraphEngine(git_repo).refresh()
    second = ProjectGraphEngine(other).refresh()

    assert not any(node.file_path == "only_other.py" for node in first.graph.nodes)
    assert any(node.file_path == "only_other.py" for node in second.graph.nodes)
    assert (git_repo / ".orqalis" / "memory" / "graph" / "graph.json").is_file()
    assert (other / ".orqalis" / "memory" / "graph" / "graph.json").is_file()


def test_git_branch_switch_refreshes_graph_and_memory_freshness(git_repo: Path) -> None:
    main_head = _git(git_repo, "rev-parse", "HEAD")
    layout = bootstrap_project_store(git_repo)
    engine = ProjectGraphEngine(git_repo)
    initial = engine.refresh()
    memory = CuratedMemoryStore(layout)
    record = DurableMemoryRecord(
        id="MEM-20260916-0001",
        category=MemoryCategory.ARCHITECTURE,
        title="Main branch answer",
        content="The main module owns the repository answer.",
        source=MemoryProvenance(
            type="repository",
            paths=("main.py",),
            content_hashes=source_hashes(git_repo, ("main.py",)),
        ),
        verified_commit=main_head,
    )
    assert initial.manifest.indexed_branch == "main"
    assert memory.status(record, main_head).freshness == MemoryFreshness.FRESH

    _git(git_repo, "checkout", "-b", "feature/branch-freshness")
    (git_repo / "main.py").write_text(
        "answer = 84\n\ndef branch_answer():\n    return answer\n",
        encoding="utf-8",
    )
    (git_repo / "feature_only.py").write_text(
        "def feature_only():\n    return True\n",
        encoding="utf-8",
    )
    _git(git_repo, "add", "--", "main.py", "feature_only.py")
    _git(
        git_repo,
        "-c",
        "user.name=Orqalis Test",
        "-c",
        "user.email=test@orqalis.invalid",
        "commit",
        "-m",
        "test: add branch-only graph state",
    )
    feature_head = _git(git_repo, "rev-parse", "HEAD")

    feature = engine.refresh()

    assert feature.manifest.indexed_branch == "feature/branch-freshness"
    assert feature.manifest.indexed_commit == feature_head
    assert {"feature_only.py", "main.py"} <= set(feature.metrics.changed_paths)
    assert any(node.file_path == "feature_only.py" for node in feature.graph.nodes)
    assert any(node.name == "branch_answer" for node in feature.graph.nodes)
    feature_status = memory.status(record, feature_head)
    assert feature_status.freshness == MemoryFreshness.STALE
    assert feature_status.changed_sources == ("main.py",)

    _git(git_repo, "checkout", "main")
    restored = engine.refresh()

    assert restored.manifest.indexed_branch == "main"
    assert restored.manifest.indexed_commit == main_head
    assert restored.metrics.deleted_files == 1
    assert not any(node.file_path == "feature_only.py" for node in restored.graph.nodes)
    assert not any(node.name == "branch_answer" for node in restored.graph.nodes)
    assert memory.status(record, main_head).freshness == MemoryFreshness.FRESH
    top_graph = load_manifest(ProjectLayout(git_repo))["graph"]
    assert isinstance(top_graph, dict)
    assert top_graph["indexed_branch"] == "main"
    assert top_graph["indexed_commit"] == main_head


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_graph_refresh_rejects_nonfinite_metadata_before_persisting(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, number: float
) -> None:
    bootstrap_project_store(git_repo)
    engine = ProjectGraphEngine(git_repo)
    graph = ProjectGraph(
        parser_version="source-ast-v5",
        nodes=(
            GraphNode(
                id="file:invalid",
                kind=GraphNodeKind.FILE,
                name="invalid.py",
                metadata={"metric": number},
            ),
        ),
    )
    monkeypatch.setattr(engine, "_assemble", lambda *_: graph)
    with pytest.raises(FilesystemFormatError, match="not valid JSON"):
        engine.refresh()
    assert not engine.graph_path.exists()
    assert not engine.manifest_path.exists()


def test_graph_refresh_recovers_overflowing_number_in_derived_cache(git_repo: Path) -> None:
    bootstrap_project_store(git_repo)
    engine = ProjectGraphEngine(git_repo)
    engine.refresh()
    cached = json.loads(engine.graph_path.read_text(encoding="utf-8"))
    cached["nodes"][0]["metadata"]["metric"] = "OVERFLOW_NUMBER"
    engine.graph_path.write_text(
        json.dumps(cached).replace('"OVERFLOW_NUMBER"', "1e999"), encoding="utf-8"
    )
    assert engine.load() is None
    repaired = engine.refresh()
    assert repaired.metrics.processed_files > 0
    assert engine.load() == repaired.graph


def test_digest_proof_reuses_validation_but_never_returned_models(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import orqalis.graph.engine as module

    bootstrap_project_store(git_repo)
    engine = ProjectGraphEngine(git_repo)
    engine.refresh()
    original_digest = module._graph_digest
    digest_calls: list[ProjectGraph] = []

    def counted_digest(graph: ProjectGraph) -> str:
        digest_calls.append(graph)
        return original_digest(graph)

    monkeypatch.setattr(module, "_graph_digest", counted_digest)
    first = engine.load()
    assert first is not None and first.nodes
    first.nodes[0].metadata["caller_mutation"] = "private"
    second = engine.load()
    assert second is not None and second is not first
    assert "caller_mutation" not in second.nodes[0].metadata
    assert len(digest_calls) == 1

    # A same-size change with restored timestamps must still invalidate the proof.
    original = engine.graph_path.read_bytes()
    stats = engine.graph_path.stat()
    name = second.nodes[0].name
    document = json.loads(original)
    document["nodes"][0]["name"] = ("x" if name[0] != "x" else "y") + name[1:]
    changed = module._graph_payload(ProjectGraph.model_validate(document)) + b"\n"
    assert len(changed) == len(original) and changed != original
    engine.graph_path.write_bytes(changed)
    os.utime(engine.graph_path, ns=(stats.st_atime_ns, stats.st_mtime_ns))
    assert engine.load() is None
    assert engine._graph_digest_proof is None
    assert len(digest_calls) == 2
    engine.graph_path.write_bytes(original)
    assert engine.load() is not None
    assert len(digest_calls) == 3


@pytest.mark.parametrize("failure", ["manifest", "missing", "duplicate", "nonfinite"])
def test_digest_proof_checks_fresh_manifest_and_invalidates_failures(
    git_repo: Path, failure: str
) -> None:
    bootstrap_project_store(git_repo)
    engine = ProjectGraphEngine(git_repo)
    engine.refresh()
    assert engine.load() is not None and engine._graph_digest_proof is not None
    if failure == "manifest":
        manifest = json.loads(engine.manifest_path.read_bytes())
        manifest["graph_sha256"] = "0" * 64
        engine.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif failure == "missing":
        engine.graph_path.unlink()
    elif failure == "duplicate":
        engine.graph_path.write_bytes(b'{"nodes":[],"nodes":[]}')
    else:
        engine.graph_path.write_bytes(b'{"generated_at":NaN}')
    assert engine.load() is None
    assert engine._graph_digest_proof is None


def test_digest_proof_is_coherent_when_another_load_updates_it(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import orqalis.graph.engine as module

    bootstrap_project_store(git_repo)
    engine = ProjectGraphEngine(git_repo)
    engine.refresh()
    assert engine.load() is not None
    original_reader = read_json_object_with_sha256

    def interleaved_read(path: Path) -> tuple[dict[str, object], str]:
        result = original_reader(path)
        engine._graph_digest_proof = ("b" * 64, "c" * 64)
        return result

    monkeypatch.setattr(module, "read_json_object_with_sha256", interleaved_read)
    assert engine.load() is not None
    assert engine._graph_digest_proof is not None
    assert (
        engine._graph_digest_proof[0] == hashlib.sha256(engine.graph_path.read_bytes()).hexdigest()
    )


def test_digest_proof_cannot_reuse_volatile_timestamp_default(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import orqalis.graph.engine as module

    bootstrap_project_store(git_repo)
    engine = ProjectGraphEngine(git_repo)
    engine.refresh()
    document = json.loads(engine.graph_path.read_bytes())
    del document["generated_at"]
    content = json.dumps(document).encode()
    engine.graph_path.write_bytes(content)
    manifest = json.loads(engine.manifest_path.read_bytes())
    engine._graph_digest_proof = (hashlib.sha256(content).hexdigest(), manifest["graph_sha256"])
    calls: list[ProjectGraph] = []
    original_digest = module._graph_digest

    def counted_digest(graph: ProjectGraph) -> str:
        calls.append(graph)
        return original_digest(graph)

    monkeypatch.setattr(module, "_graph_digest", counted_digest)
    assert engine.load() is None
    assert len(calls) == 1 and engine._graph_digest_proof is None


def test_digest_proof_clears_and_preserves_link_policy_error(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import orqalis.graph.engine as module

    bootstrap_project_store(git_repo)
    engine = ProjectGraphEngine(git_repo)
    engine.refresh()
    assert engine.load() is not None

    def denied(path: Path) -> tuple[dict[str, object], str]:
        raise PolicyDeniedError("linked project storage")

    monkeypatch.setattr(module, "read_json_object_with_sha256", denied)
    with pytest.raises(PolicyDeniedError, match="linked project storage"):
        engine.load()
    assert engine._graph_digest_proof is None


@pytest.mark.parametrize("source_kind", ["default", "same", "nested"])
def test_graph_constructor_validates_canonical_identity_once(
    git_repo: Path, source_kind: str
) -> None:
    class ObservedGit(LocalGitService):
        def __init__(self) -> None:
            super().__init__()
            self.roots: list[Path] = []
            self.common: list[Path] = []

        def root(self, path: Path) -> Path:
            self.roots.append(path)
            return super().root(path)

        def common_directory(self, path: Path) -> Path:
            self.common.append(path)
            return super().common_directory(path)

    nested = git_repo / "nested"
    nested.mkdir()
    source = None if source_kind == "default" else git_repo if source_kind == "same" else nested
    git = ObservedGit()
    engine = ProjectGraphEngine(git_repo, source_root=source, git=git)
    assert engine.root == engine.store_root == git_repo.resolve()
    assert git.roots == ([git_repo] if source is None else [git_repo, source])
    assert git.common == [git_repo.resolve()]


@pytest.mark.parametrize("phase", ["cold", "warm", "metadata", "delta"])
def test_refresh_with_status_returns_locked_full_status(git_repo: Path, phase: str) -> None:
    from orqalis.git.contracts import GitStatus

    class RecordingGit(LocalGitService):
        def __init__(self) -> None:
            super().__init__()
            self.observed: list[GitStatus] = []

        def status(self, path: Path) -> GitStatus:
            result = super().status(path)
            self.observed.append(result)
            return result

    _add_graph_fixture(git_repo)
    bootstrap_project_store(git_repo)
    git = RecordingGit()
    engine = ProjectGraphEngine(git_repo, git=git)
    if phase != "cold":
        engine.refresh()
        git.observed.clear()
    if phase == "metadata":
        _git(git_repo, "switch", "-c", "status-metadata")
    if phase == "delta":
        (git_repo / "pkg" / "helpers.py").write_text(
            "def changed_helper():\n    return 2\n", encoding="utf-8"
        )
    # Binary files are excluded from the graph, but still belong to full status.
    (git_repo / "status.bin").write_bytes(b"\x00dirty")
    result, status = engine.refresh_with_status()
    assert len(git.observed) == 1
    assert status is git.observed[0]
    assert status.repo_root == git_repo.resolve()
    assert "status.bin" in status.changed_paths
    assert "status.bin" not in result.manifest.dirty_paths
    assert result.manifest.indexed_commit == status.head
    assert result.manifest.indexed_branch == status.branch
    if phase == "warm":
        assert result.metrics.processed_files == 0
    elif phase == "metadata":
        assert status.branch == "status-metadata"
        assert result.metrics.processed_files == 0
    elif phase == "delta":
        assert result.metrics.processed_files == 1
        assert any(node.name == "changed_helper" for node in result.graph.nodes)


@pytest.mark.parametrize("override", ["root", "common_directory", "_execute"])
def test_graph_location_batch_preserves_instance_git_denial(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, override: str
) -> None:
    from orqalis.git.service import GitError, LocalGitService

    service = LocalGitService()

    def denied(*args: object) -> object:
        raise GitError("instance location denial")

    monkeypatch.setattr(service, override, denied)
    with pytest.raises(GitError, match="instance location denial"):
        ProjectGraphEngine(git_repo, git=service)
