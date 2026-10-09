"""Bounded JavaScript, TypeScript and TSX syntax extraction with Tree-sitter.

This is syntax intelligence, not an LSP/type checker. Calls retain source occurrences;
module resolution, dynamic dispatch and JSX component bindings are not asserted here.
"""

from __future__ import annotations

from bisect import bisect_right
from functools import lru_cache
from importlib.metadata import version
from typing import TYPE_CHECKING

from orqalis.graph.models import GraphNodeKind
from orqalis.graph.parsing import (
    MAX_BINDINGS,
    MAX_CALLS,
    MAX_DEPTH,
    MAX_IMPORTS,
    MAX_NAME,
    MAX_QUALIFIED_NAME,
    MAX_SYMBOLS,
    MAX_VISITS,
    CallSpec,
    ImportSpec,
    ParsedSource,
    SymbolSpec,
)
from orqalis.security.redaction import safe_diagnostic

if TYPE_CHECKING:
    from tree_sitter import Language, Node

KINDS = frozenset({"javascript", "typescript", "tsx"})
_FUNCTIONS = frozenset(
    {
        "function_declaration",
        "generator_function_declaration",
        "function_expression",
        "generator_function",
        "arrow_function",
    }
)
_CLASSES = frozenset({"class_declaration", "abstract_class_declaration", "class"})
_METHODS = frozenset({"method_definition", "method_signature", "abstract_method_signature"})


@lru_cache(maxsize=1)
def parser_identity() -> str:
    return ";".join(
        f"{name}={version(name)}"
        for name in ("tree-sitter", "tree-sitter-javascript", "tree-sitter-typescript")
    )


@lru_cache(maxsize=3)
def _language(kind: str) -> Language:
    from tree_sitter import Language

    if kind == "javascript":
        import tree_sitter_javascript

        return Language(tree_sitter_javascript.language())
    import tree_sitter_typescript

    factory = (
        tree_sitter_typescript.language_tsx
        if kind == "tsx"
        else tree_sitter_typescript.language_typescript
    )
    return Language(factory())


class _Collector:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self._line_starts = [0]
        self._line_starts.extend(index + 1 for index, value in enumerate(content) if value == 10)
        self.symbols: list[SymbolSpec] = []
        self.imports: list[ImportSpec] = []
        self.module_calls: list[CallSpec] = []
        self._calls: dict[str, list[CallSpec]] = {}
        self._bounds: dict[str, set[str]] = {}
        self.diagnostics: set[str] = set()
        self._visits = 0
        self._binding_count = 0
        self._call_count = 0

    def position(self, byte_offset: int) -> tuple[int, int]:
        # Avoid tree-sitter 0.26 Point property getters: their borrowed-reference
        # behavior can corrupt CPython on coordinates above the small-integer cache.
        # Byte coordinates keep the grammar's LF-based rows and zero-based byte columns.
        row_index = bisect_right(self._line_starts, byte_offset) - 1
        return row_index + 1, byte_offset - self._line_starts[row_index]

    def visit_budget(self) -> bool:
        self._visits += 1
        if self._visits > MAX_VISITS:
            self.diagnostics.add("visit_limit")
            return False
        return True

    def text(self, node: Node | None) -> str:
        return self.content[node.start_byte : node.end_byte].decode("utf-8") if node else ""

    def expression(self, node: Node | None, depth: int = 0) -> str:
        # Do not persist literals, receiver arguments or computed secrets as graph names.
        if node is None or depth > 32:
            return "<dynamic>"
        if node.type in {
            "identifier",
            "property_identifier",
            "type_identifier",
            "this",
            "super",
            "private_property_identifier",
        }:
            return self.text(node)[:300]
        if node.type in {"member_expression", "nested_type_identifier"}:
            owner = node.child_by_field_name("object") or node.child_by_field_name("module")
            member = node.child_by_field_name("property") or node.child_by_field_name("name")
            return f"{self.expression(owner, depth + 1)}.{self.expression(member, depth + 1)}"[:500]
        if node.type == "generic_type":
            return self.expression(node.child_by_field_name("name"), depth + 1)
        return "<dynamic>"

    def identifiers(self, node: Node | None) -> set[str]:
        if node is None:
            return set()
        values: set[str] = set()
        pending = [node]
        while pending:
            if not self.visit_budget():
                break
            item = pending.pop()
            if self._binding_count >= MAX_BINDINGS:
                self.diagnostics.add("binding_limit")
                break
            if item.type in {"identifier", "shorthand_property_identifier_pattern"}:
                if item.end_byte - item.start_byte <= MAX_NAME:
                    values.add(self.text(item))
                    self._binding_count += 1
                else:
                    self.diagnostics.add("name_limit")
            elif item.type not in {
                "type_annotation",
                "type_parameters",
                "predefined_type",
                "type_identifier",
            }:
                pending.extend(item.named_children)
        return values

    def collect(self, root: Node) -> None:
        # Iterative traversal remains safe for deeply nested untrusted project source.
        pending: list[tuple[Node, str | None, str | None, int]] = [(root, None, None, 0)]
        while pending:
            if not self.visit_budget():
                break
            node, owner, owner_kind, depth = pending.pop()
            if depth > MAX_DEPTH:
                self.diagnostics.add("depth_limit")
                continue
            kind = node.type
            if kind in {"ERROR", "comment"} or node.is_missing:
                continue
            if kind in {"import_statement", "export_statement"}:
                source = node.child_by_field_name("source")
                if source is not None:
                    # Escaped specifiers need decoding; never mistake their first fragment
                    # for a complete module and infer a false repository relationship.
                    fragments = source.named_children
                    module = (
                        self.text(fragments[0])
                        if len(fragments) == 1 and fragments[0].type == "string_fragment"
                        else ""
                    )
                    if not module:
                        self.diagnostics.add("unsupported_import_specifier")
                    if len(self.imports) >= MAX_IMPORTS:
                        self.diagnostics.add("import_limit")
                    elif module and len(module) <= 500 and safe_diagnostic(module) == module:
                        aliases: list[tuple[str, str]] = []
                        clause = next(
                            (n for n in node.named_children if n.type == "import_clause"), None
                        )
                        for item in clause.named_children if clause else []:
                            if item.type == "identifier":
                                aliases.append((self.text(item), "default"))
                            elif item.type == "namespace_import":
                                local = next(
                                    (n for n in item.named_children if n.type == "identifier"), None
                                )
                                if local:
                                    aliases.append((self.text(local), "*"))
                            elif item.type == "named_imports":
                                for specifier in item.named_children:
                                    import_name = specifier.child_by_field_name("name")
                                    local = specifier.child_by_field_name("alias") or import_name
                                    if (
                                        import_name
                                        and local
                                        and import_name.type == "identifier"
                                        and local.type == "identifier"
                                    ):
                                        aliases.append((self.text(local), self.text(import_name)))
                                    else:
                                        self.diagnostics.add("unsupported_import_alias")
                        aliases = [
                            (local, imported)
                            for local, imported in aliases
                            if len(local) <= MAX_NAME and len(imported) <= MAX_NAME
                        ]
                        if len(aliases) > 256:
                            self.diagnostics.add("import_alias_limit")
                            aliases = aliases[:256]
                        self.imports.append(
                            ImportSpec(
                                module=module,
                                line=self.position(node.start_byte)[0],
                                owner=owner,
                                names=tuple(imported for _, imported in aliases),
                                aliases=tuple(aliases),
                            )
                        )
            symbol_kind: GraphNodeKind | None = None
            name_node = node.child_by_field_name("name")
            symbol_node = node
            parameter_node = node.child_by_field_name("parameters") or node.child_by_field_name(
                "parameter"
            )
            if kind in _CLASSES:
                symbol_kind = GraphNodeKind.CLASS
            elif kind == "interface_declaration":
                symbol_kind = GraphNodeKind.INTERFACE
            elif kind in _FUNCTIONS:
                symbol_kind = GraphNodeKind.FUNCTION
            elif kind in _METHODS and owner_kind in {GraphNodeKind.CLASS, GraphNodeKind.INTERFACE}:
                symbol_kind = GraphNodeKind.METHOD
            elif kind in {"variable_declarator", "public_field_definition", "field_definition"}:
                value = node.child_by_field_name("value")
                if value and value.type in _FUNCTIONS | _CLASSES:
                    symbol_kind = (
                        GraphNodeKind.CLASS
                        if value.type in _CLASSES
                        else GraphNodeKind.METHOD
                        if owner_kind == GraphNodeKind.CLASS
                        else GraphNodeKind.FUNCTION
                    )
                    parameter_node = value.child_by_field_name(
                        "parameters"
                    ) or value.child_by_field_name("parameter")
                    # Traverse the value body directly so a named expression is not emitted twice.
                    symbol_node = value
                elif owner is not None:
                    self._bounds.setdefault(owner, set()).update(self.identifiers(name_node))
            if kind == "assignment_expression" and owner is not None:
                self._bounds.setdefault(owner, set()).update(
                    self.identifiers(node.child_by_field_name("left"))
                )
            default_export = (
                name_node is None
                and node.parent is not None
                and node.parent.type == "export_statement"
                and any(child.type == "default" for child in node.parent.children)
            )
            if symbol_kind and (
                default_export
                or (
                    name_node is not None
                    and name_node.type
                    in {
                        "identifier",
                        "property_identifier",
                        "private_property_identifier",
                        "type_identifier",
                    }
                )
            ):
                name = self.text(name_node) if name_node else "default"
                if not name or len(name) > MAX_NAME:
                    self.diagnostics.add("name_limit")
                    continue
                qualified = f"{owner}.{name}" if owner else name
                # Overloads/accessors can share a name; keep location identity explicit.
                if qualified in self._calls:
                    qualified += (
                        f"@{self.position(node.start_byte)[0]}:{self.position(node.start_byte)[1]}"
                    )
                if len(qualified) > MAX_QUALIFIED_NAME or len(self.symbols) >= MAX_SYMBOLS:
                    self.diagnostics.add("symbol_limit")
                    continue
                bases: list[str] = []
                implements: list[str] = []
                if symbol_kind in {GraphNodeKind.CLASS, GraphNodeKind.INTERFACE}:
                    for child in symbol_node.named_children:
                        if child.type == "class_heritage":
                            for clause in child.named_children:
                                if clause.type == "extends_clause":
                                    bases.extend(self.expression(n) for n in clause.named_children)
                                elif clause.type == "implements_clause":
                                    implements.extend(
                                        self.expression(n) for n in clause.named_children
                                    )
                                else:
                                    # JavaScript heritage contains the expression directly.
                                    bases.append(self.expression(clause))
                        elif child.type == "extends_type_clause":
                            bases.extend(self.expression(n) for n in child.named_children)
                self.symbols.append(
                    SymbolSpec(
                        kind=symbol_kind,
                        name=name,
                        qualified_name=qualified,
                        parent_qualified_name=owner,
                        line_start=self.position(node.start_byte)[0],
                        line_end=self.position(node.end_byte)[0],
                        byte_start=node.start_byte,
                        byte_end=node.end_byte,
                        bases=tuple(bases[:256]),
                        implements=tuple(implements[:256]),
                    )
                )
                self._calls[qualified] = []
                self._bounds[qualified] = self.identifiers(parameter_node)
                owner, owner_kind = qualified, symbol_kind
            if kind in {"call_expression", "new_expression"}:
                function = node.child_by_field_name("function") or node.child_by_field_name(
                    "constructor"
                )
                if self._call_count >= MAX_CALLS:
                    self.diagnostics.add("call_limit")
                else:
                    self._call_count += 1
                    call = CallSpec(
                        name=self.expression(function), line=self.position(node.start_byte)[0]
                    )
                    if owner is None:
                        self.module_calls.append(call)
                    else:
                        self._calls.setdefault(owner, []).append(call)
            pending.extend(
                (child, owner, owner_kind, depth + 1)
                for child in reversed(symbol_node.named_children)
            )
        self.symbols = [
            symbol.model_copy(
                update={
                    "calls": tuple(self._calls[symbol.qualified_name]),
                    "bound_names": tuple(sorted(self._bounds[symbol.qualified_name])),
                }
            )
            for symbol in self.symbols
        ]


def extract(content: bytes, kind: str, content_hash: str, parser_version: str) -> ParsedSource:
    from tree_sitter import Parser

    if kind not in KINDS:
        raise ValueError("Unsupported ECMAScript syntax parser")
    parser = Parser(_language(kind))
    tree = parser.parse(content)
    collector = _Collector(content)
    collector.collect(tree.root_node)
    return ParsedSource(
        parser_version=parser_version,
        parser_kind=kind,
        content_hash=content_hash,
        line_count=content.count(b"\n") + 1,
        syntax_error=tree.root_node.has_error,
        extraction_truncated=bool(collector.diagnostics),
        diagnostics=tuple(sorted(collector.diagnostics)),
        symbols=tuple(collector.symbols),
        imports=tuple(collector.imports),
        module_calls=tuple(collector.module_calls),
    )
