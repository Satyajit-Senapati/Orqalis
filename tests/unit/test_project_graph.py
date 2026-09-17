import json
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from orqalis.graph import (
    GraphEdge,
    GraphNode,
    GraphNodeKind,
    GraphProvenance,
    GraphRelation,
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
        if edge.relation in {GraphRelation.IMPORTS, GraphRelation.CALLS, GraphRelation.EXTENDS}
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
