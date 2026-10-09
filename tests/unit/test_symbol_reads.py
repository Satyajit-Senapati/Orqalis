"""Exact symbolic reads retain source identity, bounded output and inference evidence."""

import asyncio
from pathlib import Path

import pytest
from mcp import Client

from orqalis.domain.errors import ConflictError, InputError, NotFoundError, PolicyDeniedError
from orqalis.graph.models import GraphNodeKind, GraphProvenance
from orqalis.graph.symbols import SymbolService
from orqalis.mcp.policy import MCPPolicy
from orqalis.mcp.server import create_mcp
from orqalis.persistence.filesystem.layout import bootstrap_project_store
from tests.conftest import fixture_git
from tests.unit.test_local_store_interfaces import repository, task_fixture


def symbols(root: Path, files: dict[str, str]) -> SymbolService:
    for path, content in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8"))
    fixture_git(root, "add", ".")
    fixture_git(root, "commit", "-m", "source span fixture")
    bootstrap_project_store(root)
    return SymbolService(root)


def test_duplicate_names_and_python_decorators_have_exact_bodies(git_repo: Path) -> None:
    body = '@decorate("\U0001f9e0")\ndef helper():\n    return "first"'
    service = symbols(
        git_repo,
        {
            "first.py": body + '\n\ndef other():\n    return "unrelated"\n',
            "second.py": 'def helper():\n    return "second"\n',
        },
    )
    matches = service.find("helper")
    assert len(matches.symbols) == 2
    assert len({node.id for node in matches.symbols}) == 2
    first = service.find("helper", file_path="first.py").symbols[0]
    assert first.source_hash is not None
    response = service.body(first.id, expected_hash=first.source_hash)
    assert response.content == body
    assert response.size_chars == len(response.model_dump_json()) <= response.max_chars
    assert {node.name for node in service.outline("first.py").symbols} == {"helper", "other"}
    with pytest.raises(NotFoundError):
        service.body("helper", expected_hash=first.source_hash)


def test_same_line_javascript_and_unicode_offsets_are_separate(git_repo: Path) -> None:
    first = 'function alpha(){ return "\U0001f9e0"; }'
    second = 'function beta(){ return "two"; }'
    service = symbols(git_repo, {"pair.js": first + " " + second + "\n"})
    for name, expected in (("alpha", first), ("beta", second)):
        node = service.find(name).symbols[0]
        assert node.source_hash is not None
        assert service.body(node.id, expected_hash=node.source_hash).content == expected


def test_nested_typescript_body_does_not_include_neighbor(git_repo: Path) -> None:
    body = 'nested(value: string): string { return "\U0001f9e0" + value; }'
    service = symbols(
        git_repo,
        {"pair.ts": "class Box { " + body + " other() { return 2; } }\n"},
    )
    node = service.find("nested").symbols[0]
    assert node.source_hash is not None
    assert service.body(node.id, expected_hash=node.source_hash).content == body


def test_hash_guard_rejects_changed_and_removed_source(git_repo: Path) -> None:
    service = symbols(git_repo, {"sample.py": "def target():\n    return 1\n"})
    node = service.find("target").symbols[0]
    assert node.source_hash is not None
    (git_repo / "sample.py").write_text("def target():\n    return 2\n", encoding="utf-8")
    with pytest.raises(ConflictError, match="changed"):
        service.body(node.id, expected_hash=node.source_hash)
    refreshed = SymbolService(git_repo)
    with pytest.raises(ConflictError, match="changed"):
        refreshed.body(node.id, expected_hash=node.source_hash)
    current = refreshed.find("target").symbols[0]
    assert current.source_hash is not None
    (git_repo / "sample.py").unlink()
    with pytest.raises(ConflictError, match="unavailable"):
        refreshed.body(current.id, expected_hash=current.source_hash)


def test_budget_and_invalid_requests_fail_without_partial_body(git_repo: Path) -> None:
    functions = "\n".join(f"def helper_{index}():\n    return {index}" for index in range(40))
    service = symbols(
        git_repo,
        {"many.py": functions, "large.py": "def large():\n    # " + "x" * 4000 + "\n    pass\n"},
    )
    for result in (
        service.find("helper", max_chars=1000),
        service.outline("many.py", max_chars=1000),
    ):
        assert result.truncated
        assert result.size_chars == len(result.model_dump_json()) <= 1000
    large = service.find("large").symbols[0]
    assert large.source_hash is not None
    with pytest.raises(InputError, match="Complete symbol body"):
        service.body(large.id, expected_hash=large.source_hash, max_chars=1000)
    for path in ("../outside.py", "/outside.py", "C:/outside.py"):
        with pytest.raises((InputError, PolicyDeniedError, ValueError)):
            service.outline(path)
    with pytest.raises(InputError):
        service.find("")
    with pytest.raises(InputError):
        service.find("helper", max_chars=999)
    with pytest.raises(InputError):
        service.body(large.id, expected_hash="not-a-source-hash")
    with pytest.raises(NotFoundError):
        service.outline("missing.py")


def test_missing_or_invalid_byte_span_fails_closed(git_repo: Path) -> None:
    service = symbols(git_repo, {"sample.py": "def helper():\n    pass\n"})
    node = service.find("helper").symbols[0]
    assert node.source_hash is not None
    for metadata in ({}, {"byte_start": -1, "byte_end": 10}, {"byte_start": 0, "byte_end": 999999}):
        service.nodes[node.id] = node.model_copy(update={"metadata": metadata})
        with pytest.raises(ConflictError, match="exact source span"):
            service.body(node.id, expected_hash=node.source_hash)


def test_reference_candidates_keep_evidence_and_explicit_coverage(git_repo: Path) -> None:
    service = symbols(
        git_repo,
        {
            "sample.py": (
                "def helper():\n    pass\n"
                + "\n".join(f"def caller_{index}():\n    helper()" for index in range(10))
            )
        },
    )
    node = service.find("helper").symbols[0]
    result = service.references(node.id)
    assert result.coverage == "static_graph_candidates"
    assert result.edges and result.nodes
    assert all(edge.provenance == GraphProvenance.INFERRED for edge in result.edges)
    assert all(
        edge.evidence and edge.resolution_basis and edge.source_expressions for edge in result.edges
    )
    assert not service.references(node.id, include_inferred=False).edges
    bounded = service.references(node.id, max_chars=1000)
    assert bounded.truncated
    assert bounded.size_chars == len(bounded.model_dump_json()) <= 1000


def test_sdk_and_mcp_symbol_reads_require_source_identity(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    sdk, project, _, _ = task_fixture(root)
    node = sdk.find_project_symbols("tablet_navigation").symbols[0]
    assert node.source_hash is not None
    assert "return True" in sdk.project_symbol_body(node.id, node.source_hash).content

    async def scenario() -> None:
        policy = MCPPolicy(project_id=project.id, workspaces_root=tmp_path / "worktrees")
        async with Client(create_mcp(sdk, policy)) as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            assert {
                "find_project_symbols",
                "get_module_symbols",
                "get_symbol_body",
                "get_symbol_references",
            } <= names
            for name, arguments in (
                ("find_project_symbols", {"query": "tablet_navigation"}),
                ("get_module_symbols", {"file_path": "main.py"}),
                ("get_symbol_body", {"symbol_id": node.id, "expected_hash": node.source_hash}),
                ("get_symbol_references", {"symbol_id": node.id}),
            ):
                result = await client.call_tool(name, arguments)
                assert not result.is_error, (name, result.content)
            for name, arguments in (
                ("get_module_symbols", {"file_path": "../outside.py"}),
                ("get_symbol_body", {"symbol_id": node.id, "expected_hash": "0" * 64}),
                ("get_symbol_body", {"symbol_id": node.id}),
            ):
                result = await client.call_tool(name, arguments)
                assert result.is_error, (name, result.content)

    try:
        asyncio.run(scenario())
    finally:
        sdk.close()


def test_parser_incompleteness_is_visible_and_diagnostics_are_bounded(git_repo: Path) -> None:
    service = symbols(git_repo, {"sample.py": "def helper():\n    pass\n"})
    template = next(
        node
        for node in service.graph.nodes
        if node.kind == GraphNodeKind.FILE and node.file_path == "sample.py"
    )
    incomplete = tuple(
        template.model_copy(
            update={
                "id": f"file:partial-{index}",
                "file_path": f"partial_{index}.ts",
                "metadata": {
                    "extraction_truncated": True,
                    "extraction_diagnostics": ["symbol_limit"],
                },
            }
        )
        for index in range(40)
    )
    service.graph = service.graph.model_copy(update={"nodes": (*service.graph.nodes, *incomplete)})
    response = service.find("helper", max_chars=1000)
    assert response.source_coverage.extraction_truncated
    assert response.source_coverage.diagnostics_truncated
    assert response.truncated
    assert response.size_chars == len(response.model_dump_json()) <= 1000
    assert not service.outline("sample.py").source_coverage.extraction_truncated
    assert service.outline("partial_0.ts").source_coverage.extraction_truncated
    target = service.find("helper").symbols[0]
    assert service.references(target.id).source_coverage.extraction_truncated
