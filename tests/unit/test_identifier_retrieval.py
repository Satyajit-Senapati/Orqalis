from pathlib import Path

import pytest

from orqalis.context.builder import ProjectContextBuilder, _contains_score
from orqalis.graph.models import GraphNodeKind
from orqalis.indexing import IndexRecordKind, ProjectIndex
from orqalis.indexing.models import INDEX_VERSION
from orqalis.retrieval import lexical_terms
from tests.unit.test_project_index import _memory, _project


def test_identifier_terms_match_natural_language_without_substring_noise() -> None:
    assert {"retry_offline", "retry", "offline"} <= set(lexical_terms("retry_offline"))
    assert {"http", "request", "parser"} <= set(lexical_terms("HTTPRequestParser"))
    assert _contains_score("notification retryOffline", ("cat", "retry", "offline")) == 2


def test_index_and_context_find_identifier_parts_and_rebuild_old_indexes(tmp_path: Path) -> None:
    root = _project(tmp_path, "retrieval", "retry_offline")
    index = ProjectIndex(root)
    index.rebuild()
    for query in ("retry offline", "retry_offline", "SyncCoordinator", "sync coordinator"):
        matches = index.search(query)
        assert any(match.document.path == "sync.py" for match in matches)
    pack = ProjectContextBuilder(root).build("retry offline", 20_000)
    assert any(item.node.name.endswith("retry_offline") for item in pack.graph)
    assert pack.size_chars == len(pack.model_dump_json()) <= pack.max_chars
    import json

    manifest_path = root / ".orqalis/index/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["index_version"] = "lexical-v1"
    manifest_path.write_text(json.dumps(manifest))
    assert index.search("retry offline")
    assert json.loads(manifest_path.read_text())["index_version"] == INDEX_VERSION


def test_memory_uses_the_same_identifier_terms(tmp_path: Path) -> None:
    from orqalis.memory.curated import CuratedMemoryStore
    from orqalis.persistence.filesystem import ProjectLayout

    root = _project(tmp_path, "memory", "retry_offline")
    _memory(root, "RetryOffline policy", "RetryOffline preserves queued requests.")
    store = CuratedMemoryStore(ProjectLayout(root))
    assert store.search("retry offline")
    assert not store.search("line")


def test_definitions_win_reference_ties_without_hiding_external_calls(tmp_path: Path) -> None:
    root = _project(tmp_path, "reference-ranking", "retry_offline")
    for caller_index in range(8):
        (root / f"caller_{caller_index}.py").write_text(
            f"def consume_{caller_index}(other):\n    return other.retry_offline()\n",
            encoding="utf-8",
        )
    (root / "external.py").write_text(
        "def external(client):\n    return client.opaque_operation()\n", encoding="utf-8"
    )
    index = ProjectIndex(root)
    index.rebuild()
    matches = index.search("retry_offline", limit=100)
    definition = next(
        match
        for match in matches
        if match.document.path == "sync.py" and match.document.kind == IndexRecordKind.SYMBOL
    )
    occurrences = [match for match in matches if match.document.kind == IndexRecordKind.REFERENCE]
    assert len(occurrences) == 8
    assert all(item.score == definition.score for item in occurrences)
    assert matches.index(definition) < min(matches.index(item) for item in occurrences)
    external = index.search("opaque_operation")
    assert external[0].document.kind == IndexRecordKind.REFERENCE
    assert external[0].document.path == "external.py"
    pack = ProjectContextBuilder(root).build("retry_offline", 4000)
    assert pack.graph[0].node.file_path == "sync.py"
    assert any(item.node.name.endswith("retry_offline") for item in pack.graph)
    assert all(item.node.kind != GraphNodeKind.REFERENCE for item in pack.graph)
    assert len(pack.model_dump_json()) <= 4000


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Retry offline, retry! caf? na?ve", ("retry", "offline", "caf", "na", "ve")),
        ("x 12 a 3", ("12",)),
        ("already_lower already_lower", ("already_lower", "already", "lower")),
        ("HTTPRequestParser", ("httprequestparser", "http", "request", "parser")),
        ("", ()),
    ],
)
def test_lexical_terms_preserve_prose_and_identifier_order(
    text: str, expected: tuple[str, ...]
) -> None:
    assert lexical_terms(text) == expected
