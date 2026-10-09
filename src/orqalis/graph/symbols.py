"""Provider-neutral bounded symbolic reads over Orqalis source intelligence.

The high-level operation concept is informed by Serena. This is an original
implementation over Orqalis graph contracts; it does not embed Serena application code.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Literal, cast

from pydantic import Field

from orqalis.domain.base import Contract
from orqalis.domain.errors import ConflictError, InputError, NotFoundError
from orqalis.git.service import validate_relative_path
from orqalis.graph.engine import ProjectGraphEngine
from orqalis.graph.models import GraphEdge, GraphNode, GraphNodeKind, GraphProvenance, GraphRelation

_SYMBOL_KINDS = {
    GraphNodeKind.CLASS,
    GraphNodeKind.FUNCTION,
    GraphNodeKind.METHOD,
    GraphNodeKind.INTERFACE,
    GraphNodeKind.TEST,
}
_REFERENCE_RELATIONS = {
    GraphRelation.CALLS,
    GraphRelation.EXTENDS,
    GraphRelation.IMPLEMENTS,
    GraphRelation.REFERENCES,
    GraphRelation.USES,
}


class SymbolSourceDiagnostic(Contract):
    file_path: str
    extraction_truncated: bool
    diagnostics: tuple[str, ...] = ()


class SymbolSourceCoverage(Contract):
    extraction_truncated: bool = False
    diagnostics_truncated: bool = False
    source_diagnostics: tuple[SymbolSourceDiagnostic, ...] = ()


class SymbolMatches(Contract):
    symbols: tuple[GraphNode, ...] = ()
    parser_version: str
    source_coverage: SymbolSourceCoverage = Field(default_factory=SymbolSourceCoverage)
    coverage: Literal["syntax_symbols"] = "syntax_symbols"
    truncated: bool = False
    size_chars: int = Field(ge=0)
    max_chars: int = Field(ge=1000)


class SymbolBody(Contract):
    symbol: GraphNode
    content: str
    source_hash: str
    parser_version: str
    source_coverage: SymbolSourceCoverage = Field(default_factory=SymbolSourceCoverage)
    size_chars: int = Field(ge=0)
    max_chars: int = Field(ge=1000)


class SymbolReferences(Contract):
    symbol_id: str
    nodes: tuple[GraphNode, ...] = ()
    edges: tuple[GraphEdge, ...] = ()
    coverage: Literal["static_graph_candidates"] = "static_graph_candidates"
    parser_version: str
    source_coverage: SymbolSourceCoverage = Field(default_factory=SymbolSourceCoverage)
    truncated: bool = False
    size_chars: int = Field(ge=0)
    max_chars: int = Field(ge=1000)


def _budget(max_chars: int) -> None:
    if not 1000 <= max_chars <= 200000:
        raise InputError("Symbol response budget must be between 1000 and 200000 characters")


def _size[T: SymbolMatches | SymbolBody | SymbolReferences](result: T) -> T:
    for _ in range(4):
        actual = len(result.model_dump_json())
        if actual == result.size_chars:
            return result
        result = cast(T, result.model_copy(update={"size_chars": actual}))
    return result


class SymbolService:
    def __init__(self, root: Path, *, engine: ProjectGraphEngine | None = None) -> None:
        self.engine = engine or ProjectGraphEngine(root)
        self.graph = self.engine.refresh().graph
        self.nodes = {node.id: node for node in self.graph.nodes}

    def find(
        self,
        query: str,
        *,
        file_path: str | None = None,
        limit: int = 20,
        max_chars: int = 12000,
    ) -> SymbolMatches:
        """Discover exact IDs; a name match never authorizes an ambiguous body read."""
        _budget(max_chars)
        if not query.strip() or len(query) > 1000 or not 1 <= limit <= 100:
            raise InputError("Symbol query requires 1..1000 characters and limit 1..100")
        if file_path is not None:
            validate_relative_path(file_path)
        needle = query.casefold()
        matches = []
        for node in self.graph.nodes:
            if node.kind not in _SYMBOL_KINDS or node.metadata.get("symbol_kind") == "suite":
                continue
            if file_path is not None and node.file_path != file_path:
                continue
            qualified = str(node.metadata.get("qualified_name", node.name))
            if needle not in qualified.casefold() and needle not in node.name.casefold():
                continue
            exact = node.name.casefold() == needle or qualified.casefold() == needle
            matches.append((not exact, qualified, node.file_path or "", node.id, node))
        matches.sort(key=lambda entry: entry[:4])
        return self._matches([entry[4] for entry in matches], limit, max_chars, file_path)

    def outline(self, file_path: str, *, max_chars: int = 12000) -> SymbolMatches:
        _budget(max_chars)
        validate_relative_path(file_path)
        if not any(node.file_path == file_path for node in self.graph.nodes):
            raise NotFoundError("File is not present in the repository graph")
        nodes = [
            node
            for node in self.graph.nodes
            if node.file_path == file_path
            and node.kind in _SYMBOL_KINDS
            and node.metadata.get("symbol_kind") != "suite"
        ]
        nodes.sort(key=lambda node: (node.line_start or 0, node.id))
        return self._matches(nodes, 100, max_chars, file_path)

    def _coverage(self, file_path: str | None, max_chars: int) -> SymbolSourceCoverage:
        diagnostics: list[SymbolSourceDiagnostic] = []
        extraction_truncated = False
        diagnostics_truncated = False
        for node in self.graph.nodes:
            if node.kind != GraphNodeKind.FILE or not node.file_path:
                continue
            if file_path is not None and node.file_path != file_path:
                continue
            incomplete = node.metadata.get("extraction_truncated") is True
            raw = node.metadata.get("extraction_diagnostics")
            codes = tuple(raw) if isinstance(raw, list) else ()
            extraction_truncated |= incomplete
            if not incomplete and not codes:
                continue
            item = SymbolSourceDiagnostic(
                file_path=node.file_path, extraction_truncated=incomplete, diagnostics=codes
            )
            proposed = [value.model_dump(mode="json") for value in (*diagnostics, item)]
            if len(json.dumps(proposed)) <= max_chars // 3:
                diagnostics.append(item)
            else:
                diagnostics_truncated = True
        return SymbolSourceCoverage(
            extraction_truncated=extraction_truncated,
            diagnostics_truncated=diagnostics_truncated,
            source_diagnostics=tuple(diagnostics),
        )

    def _matches(
        self, nodes: list[GraphNode], limit: int, max_chars: int, file_path: str | None
    ) -> SymbolMatches:
        selected: list[GraphNode] = []
        coverage = self._coverage(file_path, max_chars)
        truncated = len(nodes) > limit or coverage.diagnostics_truncated
        for node in nodes[:limit]:
            candidate = _size(
                SymbolMatches(
                    symbols=(*selected, node),
                    parser_version=self.graph.parser_version,
                    source_coverage=coverage,
                    truncated=truncated,
                    size_chars=0,
                    max_chars=max_chars,
                )
            )
            if candidate.size_chars <= max_chars:
                selected.append(node)
            else:
                truncated = True
        return _size(
            SymbolMatches(
                symbols=tuple(selected),
                parser_version=self.graph.parser_version,
                source_coverage=coverage,
                truncated=truncated,
                size_chars=0,
                max_chars=max_chars,
            )
        )

    def _symbol(self, symbol_id: str) -> GraphNode:
        node = self.nodes.get(symbol_id)
        if node is None or node.kind not in _SYMBOL_KINDS or not node.file_path:
            raise NotFoundError("Exact source symbol ID is not present in the graph")
        if node.metadata.get("symbol_kind") == "suite":
            raise InputError("Test-suite file nodes are not individual source symbols")
        return node

    def body(self, symbol_id: str, *, expected_hash: str, max_chars: int = 20000) -> SymbolBody:
        """Read the indexed span only when the caller's source snapshot still matches."""
        _budget(max_chars)
        if re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
            raise InputError("Symbol body requires the SHA-256 from symbol discovery")
        node = self._symbol(symbol_id)
        if node.source_hash != expected_hash:
            raise ConflictError("Symbol source changed; discover the symbol again")
        assert node.file_path is not None
        try:
            data = self.engine._read_source(node.file_path)
        except OSError as exc:
            raise ConflictError("Symbol source is unavailable; discover the symbol again") from exc
        if data is None or hashlib.sha256(data).hexdigest() != expected_hash:
            raise ConflictError("Symbol source changed; discover the symbol again")
        start, end = node.metadata.get("byte_start"), node.metadata.get("byte_end")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(data):
            raise ConflictError("Symbol has no valid exact source span; rebuild the graph")
        try:
            content = data[start:end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ConflictError("Symbol source span is not valid UTF-8") from exc
        result = _size(
            SymbolBody(
                symbol=node,
                content=content,
                source_hash=expected_hash,
                source_coverage=self._coverage(node.file_path, max_chars),
                parser_version=self.graph.parser_version,
                size_chars=0,
                max_chars=max_chars,
            )
        )
        if result.size_chars > max_chars:
            raise InputError("Complete symbol body exceeds response budget; increase max_chars")
        return result

    def references(
        self,
        symbol_id: str,
        *,
        include_inferred: bool = True,
        limit: int = 50,
        max_chars: int = 12000,
    ) -> SymbolReferences:
        """Return witnessed static graph candidates, not exhaustive LSP references."""
        _budget(max_chars)
        self._symbol(symbol_id)
        if not 1 <= limit <= 100:
            raise InputError("Symbol reference limit must be between 1 and 100")
        edges = sorted(
            (
                edge
                for edge in self.graph.edges
                if edge.target_id == symbol_id
                and edge.relation in _REFERENCE_RELATIONS
                and (include_inferred or edge.provenance == GraphProvenance.EXTRACTED)
            ),
            key=lambda edge: edge.id,
        )
        selected: list[GraphEdge] = []
        nodes: dict[str, GraphNode] = {}
        coverage = self._coverage(None, max_chars)
        truncated = len(edges) > limit or coverage.diagnostics_truncated
        for edge in edges[:limit]:
            source = self.nodes.get(edge.source_id)
            if source is None:
                continue
            proposed_nodes = {**nodes, source.id: source}
            candidate = _size(
                SymbolReferences(
                    symbol_id=symbol_id,
                    nodes=tuple(proposed_nodes.values()),
                    edges=(*selected, edge),
                    parser_version=self.graph.parser_version,
                    source_coverage=coverage,
                    truncated=truncated,
                    size_chars=0,
                    max_chars=max_chars,
                )
            )
            if candidate.size_chars <= max_chars:
                nodes, selected = proposed_nodes, [*selected, edge]
            else:
                truncated = True
        return _size(
            SymbolReferences(
                symbol_id=symbol_id,
                nodes=tuple(nodes.values()),
                edges=tuple(selected),
                parser_version=self.graph.parser_version,
                source_coverage=coverage,
                truncated=truncated,
                size_chars=0,
                max_chars=max_chars,
            )
        )
