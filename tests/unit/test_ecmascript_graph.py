"""Real grammar fixtures for symbol locations, conservative links and cache isolation."""

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from orqalis.domain.errors import ConflictError
from orqalis.graph.ecmascript import extract
from orqalis.graph.engine import PARSER_VERSION, ProjectGraphEngine
from orqalis.graph.models import GraphNodeKind, GraphProvenance, GraphRelation
from orqalis.graph.parsing import ParsedSource
from orqalis.persistence.filesystem import bootstrap_project_store
from tests.conftest import fixture_git
from tests.unit.test_graph_provenance import _graph

SOURCE = """import Default, {sum as add, type User} from "./math";
export {sum as plus} from "./math";
export interface Result<T> extends Base { read(x: T): string; }
@sealed
export class Store extends Base implements Result<number> {
  constructor(private id: string) {}
  public load = (value: number): string => add(value);
  async read<T>(value: T) { return this.load(value); }
}
export const App = ({title}: Props) => <div>{title}</div>;
export async function outer(value: string) {
  function inner() { return value; }
  return inner();
}
"""


def facts(source: str, kind: str = "tsx") -> ParsedSource:
    content = source.encode()
    return extract(content, kind, hashlib.sha256(content).hexdigest(), PARSER_VERSION)


def test_tsx_syntax_and_exact_locations_cover_real_language_constructs() -> None:
    parsed = facts(SOURCE)
    assert not parsed.syntax_error
    symbols = {symbol.qualified_name: symbol for symbol in parsed.symbols}
    assert set(symbols) == {
        "Result",
        "Result.read",
        "Store",
        "Store.constructor",
        "Store.load",
        "Store.read",
        "App",
        "outer",
        "outer.inner",
    }
    assert symbols["Result"].kind == GraphNodeKind.INTERFACE
    assert symbols["Store.load"].kind == GraphNodeKind.METHOD
    assert symbols["Store"].bases == ("Base",)
    assert symbols["Store"].implements == ("Result",)
    assert symbols["outer.inner"].parent_qualified_name == "outer"
    assert symbols["outer.inner"].line_start == symbols["outer.inner"].line_end == 12
    assert symbols["App"].line_start == symbols["App"].line_end == 10
    assert symbols["Store.read"].calls[0].name == "this.load"
    assert symbols["Store.load"].calls[0].name == "add"
    assert parsed.imports[0].aliases == (("Default", "default"), ("add", "sum"), ("User", "User"))
    assert parsed.imports[1].module == "./math"


@pytest.mark.parametrize(
    "kind,source,expected",
    [
        ("javascript", "export function caf\u00e9(x) { return x; }", "caf\u00e9"),
        ("javascript", "const run = function named() { return 1; };", "run"),
        ("typescript", "export function map<T>(x: T): T { return x; }", "map"),
        ("tsx", "export const App = () => <div>ready</div>;", "App"),
    ],
)
def test_grammar_dialects_and_unicode(kind: str, source: str, expected: str) -> None:
    parsed = facts(source, kind)
    assert not parsed.syntax_error
    assert [symbol.name for symbol in parsed.symbols] == [expected]


def test_partial_syntax_is_reported_without_losing_intact_declarations() -> None:
    parsed = facts("export function intact() { return 1; }\nconst broken = ;\n")
    assert parsed.syntax_error
    assert any(symbol.name == "intact" for symbol in parsed.symbols)


def test_dynamic_receiver_literals_are_never_stored_in_graph_names() -> None:
    marker = "private-receiver-literal"
    javascript = facts(f"function run() {{ factory('{marker}').send(); registry['{marker}'](); }}")
    assert marker not in javascript.model_dump_json()
    python = _graph(
        {"source.py": f"def run():\n    factory('{marker}').send()\n    registry['{marker}']()\n"}
    )
    assert marker not in python.model_dump_json()
    assert any(node.name == "<dynamic>.send" for node in python.nodes)


def test_deeply_nested_source_uses_bounded_expression_walk() -> None:
    parsed = facts("function run() { " + "receiver." * 150 + "call(); }")
    assert len(parsed.symbols[0].calls[0].name) <= 500


def test_graph_integration_cache_dialects_and_dirty_rebuild(tmp_path: Path) -> None:
    root = tmp_path / "mixed"
    root.mkdir()
    fixture_git(root, "init", "-b", "main")
    files = {
        "web/App.tsx": SOURCE,
        "web/math.ts": "export function sum(value: number) { return value; }\n",
        "web/same.ts": "export function same() {}\n",
        "web/same.js": "export function same() {}\n",
        "web/ambiguous.ts": "import {same} from './same';\n",
        "web/run.mjs": "export function launch() {}\n",
        "web/run.cts": "export function launch() {}\n",
        "main.py": "def python_source():\n    return 1\n",
    }
    for path, content in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    fixture_git(root, "add", ".")
    fixture_git(root, "commit", "-m", "mixed language fixture")
    bootstrap_project_store(root, project_name="mixed")
    engine = ProjectGraphEngine(root)
    graph = engine.rebuild().graph
    nodes = {node.id: node for node in graph.nodes}
    assert any(
        node.name == "App" and node.kind == GraphNodeKind.FUNCTION and node.language == "TypeScript"
        for node in graph.nodes
    )
    assert any(node.name == "python_source" and node.language == "Python" for node in graph.nodes)
    assert any(node.name == "launch" and node.file_path == "web/run.mjs" for node in graph.nodes)
    assert any(node.name == "launch" and node.file_path == "web/run.cts" for node in graph.nodes)
    imports = [edge for edge in graph.edges if edge.relation == GraphRelation.IMPORTS]
    assert any(
        nodes[edge.source_id].file_path == "web/App.tsx"
        and nodes[edge.target_id].file_path == "web/math.ts"
        and edge.provenance == GraphProvenance.INFERRED
        for edge in imports
    )
    ambiguous = [edge for edge in imports if nodes[edge.source_id].file_path == "web/ambiguous.ts"]
    assert len(ambiguous) == 1
    assert nodes[ambiguous[0].target_id].file_path is None
    assert nodes[ambiguous[0].target_id].metadata["external"] is False
    # Imported calls are occurrences; no unsupported TS type/export resolver is implied.
    add_call = next(edge for edge in graph.edges if edge.source_expressions == ("add",))
    assert nodes[add_call.target_id].kind == GraphNodeKind.REFERENCE
    assert engine.refresh().metrics.processed_files == 0
    cached = [path.name for path in engine.cache_dir.glob("*.json")]
    assert any(name.startswith("typescript-") for name in cached)
    assert any(name.startswith("javascript-") for name in cached)
    (root / "web/math.ts").write_text(
        "export function changed(value: number) { return value; }\n", encoding="utf-8"
    )
    incremental = engine.refresh()
    assert incremental.metrics.processed_files == 1
    rebuilt = engine.rebuild()
    assert incremental.graph.nodes == rebuilt.graph.nodes
    assert incremental.graph.edges == rebuilt.graph.edges
    assert not any(
        node.name == "sum" and node.file_path == "web/math.ts" for node in rebuilt.graph.nodes
    )


def test_source_change_during_parse_cannot_poison_content_cache(tmp_path: Path) -> None:
    root = tmp_path / "race"
    root.mkdir()
    fixture_git(root, "init", "-b", "main")
    (root / "source.ts").write_text("export function old() {}", encoding="utf-8")
    fixture_git(root, "add", ".")
    fixture_git(root, "commit", "-m", "race fixture")
    bootstrap_project_store(root, project_name="race")
    engine = ProjectGraphEngine(root)
    digest = hashlib.sha256((root / "source.ts").read_bytes()).hexdigest()
    (root / "source.ts").write_text("export function changed() {}", encoding="utf-8")
    with pytest.raises(ConflictError, match="changed during graph parsing"):
        engine._parse("source.ts", digest, "typescript")
    assert not engine._cache_path(digest, "typescript").exists()


def test_default_export_and_object_methods_do_not_create_false_global_bindings() -> None:
    parsed = facts("export default () => <main/>; const config = { action() {} }; action();")
    assert [symbol.name for symbol in parsed.symbols] == ["default"]


def test_python_symbol_span_includes_decorators() -> None:
    graph = _graph({"decorated.py": "@registered\ndef handler():\n    return 1\n"})
    symbol = next(node for node in graph.nodes if node.name == "handler")
    assert symbol.line_start == 1
    assert symbol.line_end == 3


def test_credential_import_and_quoted_method_names_are_not_persisted() -> None:
    parsed = facts(
        'import value from "https://user:fixture-password@example.invalid/api";'
        'class Example { "private-string-method"() {} }'
    )
    text = parsed.model_dump_json()
    assert "fixture-password" not in text
    assert "private-string-method" not in text


def test_escaped_import_and_string_alias_cannot_create_false_or_private_facts() -> None:
    parsed = facts(
        r'import {x} from "./base\u002fsecret";'
        'import {"private-string-import" as local} from "./safe";',
        "javascript",
    )
    assert [item.module for item in parsed.imports] == ["./safe"]
    assert parsed.imports[0].aliases == ()
    assert "private-string-import" not in parsed.model_dump_json()
    assert parsed.extraction_truncated
    assert "unsupported_import_specifier" in parsed.diagnostics


def test_javascript_heritage_and_class_expression_use_visible_binding() -> None:
    parsed = facts(
        "class Base {} class Child extends Base {} "
        "const Visible = class Private extends Base { run() {} };",
        "javascript",
    )
    symbols = {item.qualified_name: item for item in parsed.symbols}
    assert set(symbols) == {"Base", "Child", "Visible", "Visible.run"}
    assert symbols["Child"].bases == symbols["Visible"].bases == ("Base",)


def test_nested_symbols_have_bounded_output_and_visible_truncation() -> None:
    parsed = facts("function inner() {" * 1000 + "inner();" + "}" * 1000, "javascript")
    assert parsed.extraction_truncated
    assert "depth_limit" in parsed.diagnostics or "symbol_limit" in parsed.diagnostics
    assert len(parsed.model_dump_json().encode()) < 100_000
    assert max(len(item.qualified_name) for item in parsed.symbols) <= 512


def test_same_line_unicode_byte_spans_exclude_adjacent_declarations() -> None:
    source = "const caf\u00e9 = () => 1; function next() { return 2; }"
    parsed = facts(source, "javascript")
    raw = source.encode()
    first, second = parsed.symbols
    assert raw[first.byte_start : first.byte_end].decode() == "caf\u00e9 = () => 1"
    assert raw[second.byte_start : second.byte_end].decode() == "function next() { return 2; }"


def test_python_parenthesized_decorator_and_unicode_exact_byte_spans() -> None:
    source = (
        "prefix = 'caf\u00e9'\n@(\n    registered\n)\ndef handler():\n"
        "    return 'caf\u00e9'\n\ndef next(): pass\n"
    )
    graph = _graph({"decorated.py": source})
    symbol = next(item for item in graph.nodes if item.name == "handler")
    assert symbol.line_start == 2
    start, end = symbol.metadata["byte_start"], symbol.metadata["byte_end"]
    assert isinstance(start, int) and isinstance(end, int)
    assert (
        source.encode()[start:end].decode()
        == "@(\n    registered\n)\ndef handler():\n    return 'caf\u00e9'"
    )


def test_python_extraction_limits_are_visible_and_do_not_infer_partial_bindings() -> None:
    import ast

    from orqalis.graph.engine import _PythonCollector

    source = "def target(): pass\ndef caller():\n" + "    x = 1\n" * 6000 + "    target()\n"
    collector = _PythonCollector(source)
    collector.visit(ast.parse(source))
    assert collector.diagnostics
    assert sum(len(item.bound_names) for item in collector.symbols) <= 5000


@pytest.mark.parametrize("separator", ["\u2028", "\u0085", "\v", "\f"])
@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_python_span_uses_physical_newlines(separator: str, newline: str) -> None:
    source = (
        f'prefix = "a{separator}b"{newline}@registered{newline}'
        f"def target():{newline}    return 1{newline}"
    )
    graph = _graph({"physical.py": source})
    symbol = next(item for item in graph.nodes if item.name == "target")
    start, end = symbol.metadata["byte_start"], symbol.metadata["byte_end"]
    assert isinstance(start, int) and isinstance(end, int)
    assert (
        source.encode()[start:end].decode()
        == f"@registered{newline}def target():{newline}    return 1"
    )


def test_javascript_block_shadowing_cannot_infer_global_inheritance() -> None:
    source = "class Base {} { const Base = replacement; class Child extends Base {} }"
    parsed = facts(source, "javascript")
    graph = ProjectGraphEngine.__new__(ProjectGraphEngine)._assemble(
        {"scope.js": parsed}, {"scope.js": parsed.content_hash}
    )
    nodes = {item.id: item for item in graph.nodes}
    edge = next(item for item in graph.edges if item.relation == GraphRelation.EXTENDS)
    assert nodes[edge.target_id].kind == GraphNodeKind.REFERENCE
    assert edge.provenance == GraphProvenance.EXTRACTED


def test_large_coordinates_do_not_corrupt_native_parser_process() -> None:
    # CPython's small-integer cache hid the native Point getter fault in short fixtures.
    # A child process makes a regression an ordinary test failure, not a lost test runner.
    program = r"""
import hashlib
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from orqalis.graph.ecmascript import extract
source = ("\r\n" * 300 + "/* caf\u00e9 \u2028 */ " + " " * 320
          + "export function panel() { return helper(); } "
          + "function panel() { return helper(); }\n").encode()
second_start = source.rindex(b"function panel")
line_start = source.rfind(b"\n", 0, second_start) + 1
for dialect in ("javascript", "typescript", "tsx"):
    for repeat in range(20):
        parsed = extract(source, dialect, hashlib.sha256(source).hexdigest(), "regression")
        assert not parsed.syntax_error
        assert parsed.line_count == 302
        assert len(parsed.symbols) == 2
        first, second = parsed.symbols
        assert first.qualified_name == "panel"
        assert second.qualified_name == f"panel@301:{second_start - line_start}"
        for symbol in parsed.symbols:
            assert symbol.line_start == symbol.line_end == 301
            assert symbol.calls[0].line == 301
            assert source[symbol.byte_start:symbol.byte_end].startswith(b"function panel")
print("60 real grammar parses with exact large-coordinate witnesses passed")
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-X",
            "dev",
            "-X",
            "faulthandler",
            "-c",
            program,
            str(Path(__file__).resolve().parents[2] / "src"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "60 real grammar parses" in result.stdout
