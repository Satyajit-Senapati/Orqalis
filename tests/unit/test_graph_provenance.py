"""Regression witnesses for syntax occurrence versus Python binding inference."""

import ast
import hashlib
from pathlib import Path

import pytest

from orqalis.graph.engine import PARSER_VERSION, ProjectGraphEngine, _PythonCollector
from orqalis.graph.models import GraphNodeKind, GraphProvenance, GraphRelation, ProjectGraph
from orqalis.graph.parsing import ParsedSource as _ParsedSource
from orqalis.persistence.filesystem.layout import bootstrap_project_store
from tests.conftest import fixture_git


def _graph(files: dict[str, str]) -> ProjectGraph:
    parsed = {}
    hashes = {}
    for path, content in files.items():
        digest = hashlib.sha256(content.encode()).hexdigest()
        hashes[path] = digest
        collector = _PythonCollector(content)
        collector.visit(ast.parse(content))
        parsed[path] = _ParsedSource(
            parser_version=PARSER_VERSION,
            parser_kind="python",
            content_hash=digest,
            line_count=len(content.splitlines()),
            symbols=tuple(item.freeze() for item in collector.symbols),
            imports=tuple(collector.imports),
            module_calls=tuple(collector.module_calls),
        )
    return ProjectGraphEngine.__new__(ProjectGraphEngine)._assemble(parsed, hashes)


@pytest.mark.parametrize("expression", ["client.helper()", "helper()", "factory().helper()"])
def test_unrelated_global_names_never_become_call_targets(expression: str) -> None:
    graph = _graph(
        {
            "unrelated.py": "def helper():\n    return 1\n",
            "caller.py": f"def run(client):\n    return {expression}\n",
        }
    )
    nodes = {node.id: node for node in graph.nodes}
    calls = [edge for edge in graph.edges if edge.relation == GraphRelation.CALLS]
    assert calls
    assert all(nodes[edge.target_id].kind == GraphNodeKind.REFERENCE for edge in calls)
    assert all(edge.provenance == GraphProvenance.EXTRACTED for edge in calls)
    assert all(edge.resolution_basis == ("syntax_occurrence",) for edge in calls)
    assert all(nodes[edge.target_id].metadata["resolution"] == "unresolved" for edge in calls)
    assert all("external" not in nodes[edge.target_id].metadata for edge in calls)


def test_supported_import_aliases_are_candidates_with_original_expressions() -> None:
    graph = _graph(
        {
            "pkg/helper.py": "def helper():\n    return 1\nclass Base:\n    pass\n",
            "pkg/caller.py": (
                "from .helper import helper as renamed, Base as Parent\n"
                "import pkg.helper as helpers\n"
                "class Child(Parent):\n    pass\n"
                "def run():\n    renamed()\n    helpers.helper()\n"
            ),
        }
    )
    nodes = {node.id: node for node in graph.nodes}
    bindings = [
        edge
        for edge in graph.edges
        if edge.relation in {GraphRelation.CALLS, GraphRelation.EXTENDS}
    ]
    assert len(bindings) == 2  # The two call expressions aggregate onto one candidate edge.
    assert all(edge.provenance == GraphProvenance.INFERRED for edge in bindings)
    assert all(edge.confidence < 1 for edge in bindings)
    assert all(edge.resolution_basis == ("import_candidate",) for edge in bindings)
    assert all(nodes[edge.target_id].file_path == "pkg/helper.py" for edge in bindings)
    calls = next(edge for edge in bindings if edge.relation == GraphRelation.CALLS)
    assert calls.source_expressions == ("helpers.helper", "renamed")
    assert len(calls.evidence) == 2


@pytest.mark.parametrize(
    "body",
    ["def run(helper):\n    helper()\n", "def run():\n    helper = lambda: 1\n    helper()\n"],
)
def test_shadowed_import_does_not_bind_to_imported_symbol(body: str) -> None:
    graph = _graph(
        {
            "helper.py": "def helper():\n    return 1\n",
            "caller.py": "from helper import helper\n" + body,
        }
    )
    nodes = {node.id: node for node in graph.nodes}
    calls = [edge for edge in graph.edges if edge.relation == GraphRelation.CALLS]
    assert calls
    assert all(nodes[edge.target_id].kind == GraphNodeKind.REFERENCE for edge in calls)


def test_lexical_and_class_candidates_do_not_claim_runtime_certainty() -> None:
    graph = _graph(
        {
            "module.py": (
                "class Service:\n"
                "    def helper(self):\n        pass\n"
                "    def run(self):\n        self.helper()\n"
                "def outer():\n"
                "    def nested():\n        pass\n"
                "    nested()\n"
            )
        }
    )
    calls = [edge for edge in graph.edges if edge.relation == GraphRelation.CALLS]
    assert len(calls) == 2
    assert {edge.resolution_basis for edge in calls} == {
        ("class_member_candidate",),
        ("lexical_candidate",),
    }
    assert all(edge.provenance == GraphProvenance.INFERRED for edge in calls)
    assert all(edge.evidence and edge.source_expressions for edge in calls)


def test_unresolved_occurrences_are_scoped_and_inheritance_is_not_suffix_bound() -> None:
    graph = _graph(
        {
            "unrelated.py": "class Base:\n    pass\n",
            "first.py": (
                "class Child(remote.Base):\n    pass\ndef run(client):\n    client.work()\n"
            ),
            "second.py": "def run(client):\n    client.work()\n",
        }
    )
    refs = [node for node in graph.nodes if node.kind == GraphNodeKind.REFERENCE]
    assert len(refs) == 3
    assert len({node.id for node in refs}) == 3
    inheritance = next(edge for edge in graph.edges if edge.relation == GraphRelation.EXTENDS)
    assert inheritance.provenance == GraphProvenance.EXTRACTED
    assert inheritance.target_id in {node.id for node in refs}


def test_candidate_graph_is_deterministic_for_input_order() -> None:
    files = {
        "helper.py": "def helper():\n    pass\n",
        "caller.py": "from helper import helper\ndef run():\n    helper()\n",
    }
    left = _graph(files)
    right = _graph(dict(reversed(tuple(files.items()))))
    assert left.nodes == right.nodes
    assert left.edges == right.edges


def test_changed_binding_matches_full_rebuild_and_invalidates_old_cache(git_repo: Path) -> None:
    helper = git_repo / "helper.py"
    helper.write_text("def helper():\n    pass\n", encoding="utf-8")
    caller = git_repo / "caller.py"
    caller.write_text("from helper import helper\ndef run():\n    helper()\n", encoding="utf-8")
    fixture_git(git_repo, "add", ".")
    fixture_git(git_repo, "commit", "-m", "graph binding fixture")
    bootstrap_project_store(git_repo)
    engine = ProjectGraphEngine(git_repo)
    before = engine.refresh()
    caller.write_text("def run(client):\n    client.helper()\n", encoding="utf-8")
    changed = engine.refresh()
    full = engine.rebuild()
    assert changed.metrics.cache_misses == 1
    assert changed.graph.nodes == full.graph.nodes
    assert changed.graph.edges == full.graph.edges
    assert not any(
        edge.provenance == GraphProvenance.INFERRED and edge.relation == GraphRelation.CALLS
        for edge in changed.graph.edges
    )
    assert any(
        edge.provenance == GraphProvenance.INFERRED and edge.relation == GraphRelation.CALLS
        for edge in before.graph.edges
    )
    # Old extraction is incompatible even if its checksum was otherwise valid.
    manifest = engine.manifest_path.read_text(encoding="utf-8")
    engine.manifest_path.write_text(
        manifest.replace(PARSER_VERSION, "python-ast-v1"), encoding="utf-8"
    )
    assert engine.load() is None
    rebuilt = engine.refresh()
    assert rebuilt.metrics.processed_files == rebuilt.metrics.total_files
    assert rebuilt.graph.nodes == full.graph.nodes
    assert rebuilt.graph.edges == full.graph.edges
