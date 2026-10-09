"""Compatibility assertions are exact semantic contracts, not a relaxed pass gate."""

import copy
import runpy
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from orqalis.graph import GraphNodeKind, GraphProvenance, GraphRelation

ROOT = Path(__file__).resolve().parents[2]
FREEZE = runpy.run_path(str(ROOT / "scripts/freeze_contract_tests.py"))


def check_graph(root: Path, *, legacy: bool = False) -> dict[str, Any]:
    (root / "pkg").mkdir()
    (root / "pkg/service.py").write_text("# evidence\n" * 10, encoding="utf-8")
    specs = (
        ("service", "Service", "pkg/service.py", GraphNodeKind.CLASS),
        ("base", "Base", "pkg/base.py", GraphNodeKind.CLASS),
        ("run", "run", "pkg/service.py", GraphNodeKind.METHOD),
        ("helper", "helper", "pkg/helpers.py", GraphNodeKind.FUNCTION),
        ("make", "make_service", "pkg/service.py", GraphNodeKind.FUNCTION),
        ("unknown", "remote.work", "pkg/service.py", GraphNodeKind.REFERENCE),
    )
    nodes = [
        SimpleNamespace(id=i, name=n, file_path=p, kind=k, metadata={"resolution": "unresolved"})
        for i, n, p, k in specs
    ]
    edges = []
    for source, target, relation in (
        ("service", "base", GraphRelation.EXTENDS),
        ("run", "helper", GraphRelation.CALLS),
        ("make", "service", GraphRelation.CALLS),
        ("run", "unknown", GraphRelation.CALLS),
    ):
        occurrence = target == "unknown"
        edges.append(
            SimpleNamespace(
                source_id=source,
                target_id=target,
                relation=relation,
                provenance=GraphProvenance.EXTRACTED
                if legacy or occurrence
                else GraphProvenance.INFERRED,
                confidence=1 if legacy or occurrence else 0.75,
                evidence=("pkg/service.py:4",),
                source_expressions=("expression",),
                resolution_basis=("syntax_occurrence" if occurrence else "import_candidate",),
            )
        )
    profile = FREEZE["LEGACY_PROFILE"] if legacy else FREEZE["CURRENT_PROFILE"]
    result = SimpleNamespace(
        graph=SimpleNamespace(nodes=nodes, edges=edges, parser_version=profile),
        manifest=SimpleNamespace(parser_version=profile),
    )
    return {
        "result": result,
        "git_repo": root,
        "GraphNodeKind": GraphNodeKind,
        "GraphRelation": GraphRelation,
        "GraphProvenance": GraphProvenance,
    }


def run_assertions(values: dict[str, Any]) -> None:
    exec(compile(textwrap.dedent(FREEZE["AMENDED"]), "compatibility-assertions", "exec"), values)


@pytest.mark.parametrize("legacy", [False, True])
def test_exact_declared_semantics_pass(tmp_path: Path, legacy: bool) -> None:
    run_assertions(check_graph(tmp_path, legacy=legacy))


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_profile",
        "manifest_mismatch",
        "extracted_candidate",
        "certain_candidate",
        "missing_basis",
        "unknown_basis",
        "missing_expression",
        "invalid_evidence",
        "empty_bindings",
        "missing_target_witness",
        "inferred_occurrence",
        "legacy_inferred",
    ],
)
def test_semantic_or_structural_regression_never_passes(tmp_path: Path, mutation: str) -> None:
    values = check_graph(tmp_path)
    result = values["result"]
    edge = result.graph.edges[0]
    if mutation == "unknown_profile":
        result.graph.parser_version = result.manifest.parser_version = "unreviewed"
    elif mutation == "manifest_mismatch":
        result.manifest.parser_version = "different"
    elif mutation == "extracted_candidate":
        edge.provenance = GraphProvenance.EXTRACTED
    elif mutation == "certain_candidate":
        edge.confidence = 1
    elif mutation == "missing_basis":
        edge.resolution_basis = ()
    elif mutation == "unknown_basis":
        edge.resolution_basis = ("global_last_name_guess",)
    elif mutation == "missing_expression":
        edge.source_expressions = ()
    elif mutation == "invalid_evidence":
        edge.evidence = ("pkg/service.py:999",)
    elif mutation == "empty_bindings":
        result.graph.edges = []
    elif mutation == "missing_target_witness":
        edge.target_id = "helper"
    elif mutation == "inferred_occurrence":
        result.graph.edges[-1].provenance = GraphProvenance.INFERRED
    else:
        result.graph.parser_version = result.manifest.parser_version = FREEZE["LEGACY_PROFILE"]
    with pytest.raises(AssertionError):
        run_assertions(values)


def test_amendment_changes_only_declared_block_and_preserves_selection() -> None:
    original = FREEZE["baseline_files"]()
    amended = copy.copy(original)
    path = FREEZE["GRAPH_TEST"]
    amended[path] = FREEZE["amend"](original[path])
    assert [p for p in original if original[p] != amended[p]] == [path]
    assert (
        amended[path].replace(FREEZE["AMENDED"].encode(), FREEZE["ORIGINAL"].encode())
        == original[path]
    )
    paths = [p for p in original if p.endswith(".py")]
    assert FREEZE["declarations"](original, paths) == FREEZE["declarations"](amended, paths)
    with pytest.raises(ValueError, match="assertion changed"):
        FREEZE["amend"](amended[path])


def test_frozen_tree_is_idempotent_and_refuses_mutation_or_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write = FREEZE["write_frozen"]
    monkeypatch.setitem(write.__globals__, "REPO", tmp_path)
    root = tmp_path / ".tools/research/contract-tests-v1"
    files = {"tests/test_example.py": b"def test_one(): pass\n"}
    write(root, files)
    write(root, files)
    with pytest.raises(ValueError, match="refusing to overwrite"):
        write(root, {"tests/test_example.py": b"changed"})
    assert (root / "tests/test_example.py").read_bytes() == files["tests/test_example.py"]
    with pytest.raises(ValueError, match="must be a child"):
        write(tmp_path / "outside", files)


def test_profile_versions_and_lf_fixture_are_exact_and_reproducible() -> None:
    original = FREEZE["baseline_files"]()
    graph = original[FREEZE["GRAPH_TEST"]]
    first = FREEZE["amend"](graph, "v1")
    second = FREEZE["amend"](graph, "v2")
    third = FREEZE["amend"](graph, "v3")
    assert b"source-ast-v4;" in first and b"source-ast-v5;" not in first
    assert b"source-ast-v5;" in second and b"source-ast-v4;" not in second
    assert third == second

    fixture = original[FREEZE["FIXTURE_TEST"]]
    fixed = FREEZE["amend_fixture"](fixture)
    assert (
        fixed.replace(FREEZE["LF_FIXTURE"].encode(), FREEZE["ORIGINAL_FIXTURE"].encode()) == fixture
    )
    assert b'.write_bytes(b"answer = 42\\n")' in fixed
    amended = {**original, FREEZE["GRAPH_TEST"]: third, FREEZE["FIXTURE_TEST"]: fixed}
    assert {path for path in original if original[path] != amended[path]} == {
        FREEZE["GRAPH_TEST"],
        FREEZE["FIXTURE_TEST"],
    }
    paths = [path for path in original if path.endswith(".py")]
    assert FREEZE["declarations"](original, paths) == FREEZE["declarations"](amended, paths)
    with pytest.raises(ValueError, match="Unknown reviewed"):
        FREEZE["amend"](graph, "v4")
    with pytest.raises(ValueError, match="fixture changed"):
        FREEZE["amend_fixture"](fixed)


@pytest.mark.parametrize("launch_form", ["console", "module", "isolated-module"])
def test_contract_guard_binds_actual_anyio_children(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, launch_form: str
) -> None:
    import asyncio
    import json
    import os
    import subprocess
    import sys

    import anyio

    source = tmp_path / "selected"
    package = source / "src/orqalis"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("__version__ = 'selected-baseline'\n")
    (package / "__main__.py").write_text(
        "import json, os, sys, orqalis\n"
        "print(json.dumps({'version': orqalis.__version__, 'source': orqalis.__file__, "
        "'args': sys.argv[1:], 'cwd': os.getcwd(), 'env': os.environ['GUARD_WITNESS']}))\n"
    )
    caller = tmp_path / "caller"
    caller.mkdir()
    poison = caller / "orqalis"
    poison.mkdir()
    (poison / "__init__.py").write_text("__version__ = 'wrong-cwd-source'\n")
    audit = tmp_path / "children.jsonl"
    # Both overrides are confined to this test; restoring Popen alone leaves the
    # async guard installed on subsequent tests' event loops.
    monkeypatch.setattr(subprocess, "Popen", subprocess.Popen)
    monkeypatch.setattr(
        asyncio.BaseEventLoop, "subprocess_exec", asyncio.BaseEventLoop.subprocess_exec
    )
    runner = runpy.run_path(str(ROOT / "scripts/run_quality_contracts.py"))
    runner["install_child_source_guard"](source, audit)
    tails = ["--probe", "space argument"]
    command = {
        "console": [str(tmp_path / "nonexistent-installed/orqalis.exe"), *tails],
        "module": [sys.executable, "-m", "orqalis", *tails],
        "isolated-module": [sys.executable, "-I", "-m", "orqalis", *tails],
    }[launch_form]

    async def invoke(argv: list[str]) -> bytes:
        async with await anyio.open_process(
            argv,
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=caller,
            env={**os.environ, "GUARD_WITNESS": "preserved"},
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ) as process:
            assert process.stdout is not None
            output = bytearray()
            while True:
                try:
                    output.extend(await process.stdout.receive())
                except anyio.EndOfStream:
                    break
            assert await process.wait() == 0
            return bytes(output)

    result = json.loads(asyncio.run(invoke(command)))
    assert result["version"] == "selected-baseline"
    assert Path(result["source"]).resolve() == (package / "__init__.py").resolve()
    assert result["args"] == tails
    assert Path(result["cwd"]).resolve() == caller.resolve()
    assert result["env"] == "preserved"
    unrelated = [sys.executable, "-I", "-c", "print('workspace-command')"]
    assert asyncio.run(invoke(unrelated)).strip() == b"workspace-command"
    records = [json.loads(line) for line in audit.read_text().splitlines()]
    assert len(records) == 1 and records[0]["selected_source"] == str(source)
