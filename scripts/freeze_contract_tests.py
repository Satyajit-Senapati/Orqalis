"""Freeze shared G01 compatibility contracts from the immutable baseline.

This does not alter the dataset, production source, original captures or contract runner.
Unknown parser profiles and any unexpected original assertion fail closed. Existing
frozen trees are verified byte-for-byte, never overwritten.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import io
import json
import runpy
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
BASELINE = "b8506f7d9c471516fe4b21c9caa735a7a7909af6"
GRAPH_TEST = "tests/unit/test_project_graph.py"
FIXTURE_TEST = "tests/conftest.py"
GRAPH_NODE = f"{GRAPH_TEST}::test_python_ast_graph_and_persisted_manifest"
LEGACY_PROFILE = "python-ast-v1"
CURRENT_PROFILE = (
    "source-ast-v5;tree-sitter=0.26.0;tree-sitter-javascript=0.25.0;tree-sitter-typescript=0.23.2"
)
HELPERS = runpy.run_path(str(REPO / "scripts/benchmark_quality.py"))
ORIGINAL = """    assert all(
        edge.provenance == GraphProvenance.EXTRACTED
        for edge in result.graph.edges
        if edge.relation in {GraphRelation.IMPORTS, GraphRelation.CALLS, GraphRelation.EXTENDS}
    )
"""
AMENDED_V1 = """    # G01 compatibility-v1: exact declared semantics, never a provenance waiver.
    profiles = {
        "python-ast-v1": "legacy_extracted_bindings",
        "source-ast-v4;tree-sitter=0.26.0;tree-sitter-javascript=0.25.0;"
        "tree-sitter-typescript=0.23.2": "candidate_bindings",
    }
    assert result.graph.parser_version == result.manifest.parser_version
    assert result.graph.parser_version in profiles, "Unreviewed parser semantics"
    profile = profiles[result.graph.parser_version]
    assert all(
        edge.provenance == GraphProvenance.EXTRACTED
        for edge in result.graph.edges
        if edge.relation == GraphRelation.IMPORTS
    )
    nodes = {node.id: node for node in result.graph.nodes}
    bindings = tuple(
        edge
        for edge in result.graph.edges
        if edge.relation in {GraphRelation.CALLS, GraphRelation.EXTENDS}
    )
    assert bindings
    for edge in bindings:
        assert edge.source_id in nodes and edge.target_id in nodes
        assert edge.evidence
        for location in edge.evidence:
            path, line = location.rsplit(":", 1)
            assert path == nodes[edge.source_id].file_path
            assert line.isdigit() and 1 <= int(line) <= len(
                (git_repo / path).read_text(encoding="utf-8").splitlines()
            )
        if profile == "legacy_extracted_bindings":
            # Preserve the documented old contract without calling it sound binding proof.
            assert edge.provenance == GraphProvenance.EXTRACTED
            assert edge.confidence == 1
        else:
            assert edge.source_expressions and all(edge.source_expressions)
            target = nodes[edge.target_id]
            if target.kind == GraphNodeKind.REFERENCE:
                assert edge.provenance == GraphProvenance.EXTRACTED
                assert edge.confidence == 1
                assert edge.resolution_basis == ("syntax_occurrence",)
                assert target.metadata["resolution"] == "unresolved"
            else:
                assert edge.provenance == GraphProvenance.INFERRED
                assert 0 < edge.confidence < 1
                assert edge.resolution_basis
                assert set(edge.resolution_basis) <= {
                    "lexical_candidate", "import_candidate", "class_member_candidate"
                }
    witnessed = {
        (
            nodes[edge.source_id].file_path,
            nodes[edge.source_id].name,
            nodes[edge.target_id].file_path,
            nodes[edge.target_id].name,
            str(edge.relation),
        )
        for edge in bindings
    }
    assert {
        ("pkg/service.py", "Service", "pkg/base.py", "Base", "EXTENDS"),
        ("pkg/service.py", "run", "pkg/helpers.py", "helper", "CALLS"),
        ("pkg/service.py", "make_service", "pkg/service.py", "Service", "CALLS"),
    } <= witnessed
"""


AMENDED = AMENDED_V1.replace("compatibility-v1", "compatibility-v2").replace(
    "source-ast-v4;", "source-ast-v5;"
)
# v3 retains the v2 graph contract and makes the shared Git fixture byte-stable
# across Windows and Unix. Only the fixture setup is changed, not an assertion.
ORIGINAL_FIXTURE = (
    '    (repo / "pyproject.toml").write_text(\'[project]\\nna'
    'me = "fixture"\\n\', encoding="utf-8")\n    (repo / "main.'
    'py").write_text("answer = 42\\n", encoding="utf-8")\n    '
    '(repo / "AGENTS.md").write_text("Run tests before deliv'
    'ery.\\n", encoding="utf-8")\n    (repo / "tests").mkdir()'
    '\n    (repo / "tests/test_main.py").write_text("def test'
    '_answer():\\n    assert 42 == 42\\n")\n'
)
LF_FIXTURE = (
    '    (repo / "pyproject.toml").write_bytes(b\'[project]\\n'
    'name = "fixture"\\n\')\n    (repo / "main.py").write_bytes'
    '(b"answer = 42\\n")\n    (repo / "AGENTS.md").write_bytes'
    '(b"Run tests before delivery.\\n")\n    (repo / "tests").'
    'mkdir()\n    (repo / "tests/test_main.py").write_bytes(b'
    '"def test_answer():\\n    assert 42 == 42\\n")\n'
)


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def fingerprint(files: dict[str, bytes]) -> dict[str, Any]:
    digest = hashlib.sha256()
    inventory = []
    for path, content in sorted(files.items()):
        digest.update(path.encode() + b"\0" + content + b"\0")
        inventory.append({"path": path, "sha256": sha256(content), "bytes": len(content)})
    return {"sha256": digest.hexdigest(), "files": inventory}


def baseline_files() -> dict[str, bytes]:
    archive = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={REPO.as_posix()}",
            "-C",
            str(REPO),
            "archive",
            "--format=tar",
            BASELINE,
            "tests",
            "pyproject.toml",
        ],
        capture_output=True,
        check=True,
        env=HELPERS["controlled_environment"](),
    ).stdout
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        for member in stream:
            if member.isdir():
                continue
            path = Path(member.name)
            if (
                not member.isfile()
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in member.name
                or not (member.name.startswith("tests/") or member.name == "pyproject.toml")
            ):
                raise ValueError("Unexpected frozen test archive member")
            content = stream.extractfile(member)
            assert content is not None
            files[member.name] = content.read()
    if GRAPH_TEST not in files:
        raise ValueError("Baseline archive lacks the declared graph test")
    return files


def amend(original: bytes, fixture_version: str = "v2") -> bytes:
    text = original.decode("utf-8")
    if text.count(ORIGINAL) != 1:
        raise ValueError("Original frozen provenance assertion changed")
    if fixture_version not in {"v1", "v2", "v3"}:
        raise ValueError("Unknown reviewed compatibility fixture version")
    replacement = AMENDED if fixture_version in {"v2", "v3"} else AMENDED_V1
    amended = text.replace(ORIGINAL, replacement, 1)
    ast.parse(amended)
    return amended.encode("utf-8")


def amend_fixture(original: bytes) -> bytes:
    text = original.decode("utf-8")
    if text.count(ORIGINAL_FIXTURE) != 1:
        raise ValueError("Original frozen Git fixture changed")
    amended = text.replace(ORIGINAL_FIXTURE, LF_FIXTURE, 1)
    ast.parse(amended)
    return amended.encode("utf-8")


def declarations(files: dict[str, bytes], paths: list[str]) -> str:
    """Fingerprint test names, parameterization and signatures independently of bodies."""
    result = []
    for path in paths:
        tree = ast.parse(files[path])
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
                "test_"
            ):
                result.append(
                    (
                        path,
                        node.name,
                        ast.dump(node.args),
                        [ast.dump(d) for d in node.decorator_list],
                    )
                )
    return sha256(json.dumps(result, sort_keys=True).encode())


def write_frozen(root: Path, files: dict[str, bytes]) -> None:
    allowed = (REPO / ".tools/research").resolve()
    root = root.resolve()
    if root == allowed or not root.is_relative_to(allowed):
        raise ValueError("Frozen test root must be a child of this repository's .tools/research")
    if root.exists():
        actual = {
            p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*")
            if p.is_file()
            and not {"__pycache__", ".pytest_cache"}.intersection(p.parts)
            and p.suffix not in {".pyc", ".pyo"}
        }
        if actual != files:
            raise ValueError("Existing frozen test tree differs; refusing to overwrite evidence")
        return
    for relative, content in files.items():
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)


def parser_profile(source: Path) -> str:
    code = (
        "import sys;from pathlib import Path;source=Path(sys.argv[1]);"
        "sys.path.insert(0,str(source/'src'));import orqalis;"
        "assert Path(orqalis.__file__).resolve().is_relative_to(source/'src');"
        "from orqalis.graph.engine import PARSER_VERSION;print(PARSER_VERSION)"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, str(source)],
        capture_output=True,
        text=True,
        check=True,
        env=HELPERS["controlled_environment"](),
        timeout=60,
    )
    return result.stdout.strip()


def graph_validation(source: Path, tests: Path, output: Path) -> dict[str, Any]:
    junit = output.with_suffix(".junit.xml")
    code = (
        "import sys;from pathlib import Path;source=Path(sys.argv.pop(1));"
        "tests=Path(sys.argv.pop(1));sys.path[:0]=[str(source/'src'),str(tests)];"
        "import orqalis;assert Path(orqalis.__file__).resolve().is_relative_to(source/'src');"
        "import pytest;raise SystemExit(pytest.main(sys.argv[1:]))"
    )
    command = [
        sys.executable,
        "-I",
        "-c",
        code,
        str(source),
        str(tests),
        "-q",
        "-o",
        "addopts=",
        "--rootdir",
        str(tests),
        "--confcutdir",
        str(tests),
        "--junitxml",
        str(junit),
        str(tests / GRAPH_NODE),
    ]
    result = subprocess.run(
        command,
        cwd=tests,
        env=HELPERS["controlled_environment"](),
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    output.write_text(result.stdout + result.stderr, encoding="utf-8")
    summary = HELPERS["contract_junit"](junit, [GRAPH_TEST])
    return {
        "exit_code": result.returncode,
        "junit": summary,
        "log": output.name,
        "junit_sha256": sha256(junit.read_bytes()),
        "log_sha256": sha256(output.read_bytes()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-source", type=Path, default=REPO / ".tools/research/baseline-b8506f7"
    )
    parser.add_argument("--current-source", type=Path, default=REPO)
    parser.add_argument("--fixture-version", choices=("v1", "v2", "v3"), default="v3")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--validate", action="store_true", help="Run only the amended graph node twice"
    )
    args = parser.parse_args()
    sources = {"baseline": args.baseline_source.resolve(), "current": args.current_source.resolve()}
    profiles = {
        "baseline": LEGACY_PROFILE,
        "current": CURRENT_PROFILE
        if args.fixture_version in {"v2", "v3"}
        else CURRENT_PROFILE.replace("source-ast-v5;", "source-ast-v4;"),
    }
    before = {label: HELPERS["source_fingerprint"](root) for label, root in sources.items()}
    for label, root in sources.items():
        if parser_profile(root) != profiles[label]:
            raise ValueError(f"Unreviewed {label} parser profile")
    original = baseline_files()
    patched = {**original, GRAPH_TEST: amend(original[GRAPH_TEST], args.fixture_version)}
    if args.fixture_version == "v3":
        patched[FIXTURE_TEST] = amend_fixture(original[FIXTURE_TEST])
    dataset_path = REPO / "benchmarks/engineering_cases.json"
    dataset_bytes = dataset_path.read_bytes()
    dataset = json.loads(dataset_bytes)
    HELPERS["validate_dataset"](dataset)
    selected = sorted({path for case in dataset["cases"] for path in case["contract_tests"]})
    if declarations(original, selected) != declarations(patched, selected):
        raise ValueError("Compatibility amendment changed selected test declarations")
    tests = (
        args.output_root or REPO / f".tools/research/contract-tests-{args.fixture_version}"
    ).resolve()
    write_frozen(tests, patched)
    manifest = (
        args.manifest
        or REPO / f"docs/quality/evidence/contract-compatibility-{args.fixture_version}.json"
    ).resolve()
    manifest.parent.mkdir(parents=True, exist_ok=True)
    patch_path = manifest.with_suffix(".patch")
    patch = "".join(
        "".join(
            difflib.unified_diff(
                original[path].decode().splitlines(keepends=True),
                patched[path].decode().splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )
        for path in (GRAPH_TEST, FIXTURE_TEST)
        if original[path] != patched[path]
    ).encode()
    patch_path.write_bytes(patch)
    validation = {}
    if args.validate:
        for label, root in sources.items():
            validation[label] = graph_validation(
                root, tests, manifest.with_name(f"{manifest.stem}-{label}.log")
            )
    after = {label: HELPERS["source_fingerprint"](root) for label, root in sources.items()}
    report = {
        "schema_version": 1,
        "fixture_id": f"contract-compatibility-{args.fixture_version}",
        "baseline_revision": BASELINE,
        "amended_node": GRAPH_NODE,
        "fixture_amendment": FIXTURE_TEST if args.fixture_version == "v3" else None,
        "reason": (
            "G01 separates extracted syntax occurrences from inferred binding candidates; "
            "v2 pins the source-ast-v5 byte-offset parser correction; "
            "v3 pins LF bytes in the shared Git fixture across platforms."
        ),
        "scope": (
            "Legacy compatibility and strict current semantics; v3 changes only "
            "fixture setup bytes, with no skip/xfail/waiver."
        ),
        "raw_captures": "Original contract captures remain unmodified and retain all failures.",
        "dataset_sha256": sha256(dataset_bytes),
        "selected_test_paths": selected,
        "selected_test_declarations_sha256": declarations(original, selected),
        "selection_declarations_unchanged": True,
        "original_test_tree": fingerprint(original),
        "patched_test_tree": fingerprint(patched),
        "original_runner_tests_sha256": fingerprint(
            {p: b for p, b in original.items() if p.endswith(".py") or p == "pyproject.toml"}
        )["sha256"],
        "patched_runner_tests_sha256": fingerprint(
            {p: b for p, b in patched.items() if p.endswith(".py") or p == "pyproject.toml"}
        )["sha256"],
        "original_graph_test_sha256": sha256(original[GRAPH_TEST]),
        "patched_graph_test_sha256": sha256(patched[GRAPH_TEST]),
        "patch": patch_path.name,
        "patch_sha256": sha256(patch),
        "generator_sha256": sha256(Path(__file__).read_bytes()),
        "sources": {
            label: {"expected_parser_profile": profiles[label], "inventory": before[label]}
            for label in sources
        },
        "sources_stable": before == after,
        "tests_root": str(tests),
        "validation": validation,
    }
    if dataset_path.read_bytes() != dataset_bytes:
        raise RuntimeError("Dataset changed while freezing contracts")
    manifest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "manifest": str(manifest),
                "tests_root": str(tests),
                "sources_stable": report["sources_stable"],
                "validation": validation,
            },
            indent=2,
        )
    )
    if before != after or any(
        v["exit_code"] or not v["junit"]["passed"] for v in validation.values()
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
