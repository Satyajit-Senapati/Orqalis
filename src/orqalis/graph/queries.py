"""Bounded graph exploration with source evidence preserved in every result.

Inspired by Graphify's explainable graph navigation; implemented over Orqalis's
own graph contracts and filesystem authority without an external graph service.
"""

from collections import defaultdict, deque
from typing import Literal

from pydantic import AwareDatetime

from orqalis.domain.base import Contract
from orqalis.domain.errors import InputError, NotFoundError
from orqalis.graph.models import GraphEdge, GraphNode, GraphProvenance, ProjectGraph

Direction = Literal["incoming", "outgoing", "both"]


class GraphTraversal(Contract):
    roots: tuple[str, ...]
    direction: Direction
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    depths: dict[str, int]
    truncated: bool
    generated_at: AwareDatetime
    parser_version: str


class GraphPath(Contract):
    found: bool
    nodes: tuple[GraphNode, ...] = ()
    edges: tuple[GraphEdge, ...] = ()
    visited_nodes: int
    truncated: bool
    generated_at: AwareDatetime
    parser_version: str


class GraphQueries:
    """Return deterministic breadth-first witnesses, not inferred impact certainty."""

    def __init__(self, graph: ProjectGraph) -> None:
        self.graph = graph
        self.nodes = {node.id: node for node in graph.nodes}

    @staticmethod
    def _limits(max_depth: int, max_nodes: int, min_confidence: float) -> None:
        if not 1 <= max_depth <= 20 or not 1 <= max_nodes <= 1000:
            raise InputError("Graph queries require depth 1..20 and node limit 1..1000")
        if not 0 <= min_confidence <= 1:
            raise InputError("Graph confidence must be between 0 and 1")

    def _adjacency(
        self, direction: Direction, include_inferred: bool, min_confidence: float
    ) -> dict[str, list[tuple[str, GraphEdge]]]:
        if direction not in {"incoming", "outgoing", "both"}:
            raise InputError("Graph direction must be incoming, outgoing, or both")
        result: dict[str, list[tuple[str, GraphEdge]]] = defaultdict(list)
        for edge in sorted(self.graph.edges, key=lambda item: item.id):
            if edge.source_id not in self.nodes or edge.target_id not in self.nodes:
                continue
            if edge.confidence < min_confidence:
                continue
            if not include_inferred and edge.provenance != GraphProvenance.EXTRACTED:
                continue
            if direction in {"outgoing", "both"}:
                result[edge.source_id].append((edge.target_id, edge))
            if direction in {"incoming", "both"}:
                result[edge.target_id].append((edge.source_id, edge))
        for neighbors in result.values():
            neighbors.sort(key=lambda pair: (pair[0], pair[1].id))
        return result

    def _roots(self, node_or_path: str) -> tuple[str, ...]:
        if node_or_path in self.nodes:
            return (node_or_path,)
        matches = tuple(sorted(n.id for n in self.nodes.values() if n.file_path == node_or_path))
        if not matches:
            raise NotFoundError("No graph node or repository-relative file matches the query")
        return matches

    def impact(
        self,
        node_or_path: str,
        *,
        max_depth: int = 3,
        max_nodes: int = 100,
        include_inferred: bool = True,
        min_confidence: float = 0,
    ) -> GraphTraversal:
        """Find incoming dependents of a node, or every symbol in a source file.

        Edges are a discovery forest with original direction, evidence and confidence.
        Results identify candidates for inspection, not proof that a change is unsafe.
        """
        self._limits(max_depth, max_nodes, min_confidence)
        roots = self._roots(node_or_path)
        adjacent = self._adjacency("incoming", include_inferred, min_confidence)
        selected = roots[:max_nodes]
        depths = dict.fromkeys(selected, 0)
        queue = deque(selected)
        witnesses: list[GraphEdge] = []
        truncated = len(roots) > len(selected)
        while queue:
            source = queue.popleft()
            for target, edge in adjacent[source]:
                if target in depths:
                    continue
                if depths[source] >= max_depth or len(depths) >= max_nodes:
                    truncated = True
                    continue
                depths[target] = depths[source] + 1
                witnesses.append(edge)
                queue.append(target)
        return GraphTraversal(
            roots=selected,
            direction="incoming",
            nodes=tuple(self.nodes[key] for key in depths),
            edges=tuple(witnesses),
            depths=depths,
            truncated=truncated,
            generated_at=self.graph.generated_at,
            parser_version=self.graph.parser_version,
        )

    def shortest_path(
        self,
        source_id: str,
        target_id: str,
        *,
        max_depth: int = 8,
        max_nodes: int = 1000,
        direction: Direction = "outgoing",
        include_inferred: bool = True,
        min_confidence: float = 0,
    ) -> GraphPath:
        """Return a shortest hop path between exact IDs within an explicit search budget."""
        self._limits(max_depth, max_nodes, min_confidence)
        if source_id not in self.nodes or target_id not in self.nodes:
            raise NotFoundError("Source and target must be graph node IDs")
        adjacent = self._adjacency(direction, include_inferred, min_confidence)
        queue = deque([source_id])
        depths = {source_id: 0}
        parents: dict[str, tuple[str, GraphEdge]] = {}
        truncated = False
        found = source_id == target_id
        while queue and not found:
            source = queue.popleft()
            for target, edge in adjacent[source]:
                if target in depths:
                    continue
                if depths[source] >= max_depth or len(depths) >= max_nodes:
                    truncated = True
                    continue
                depths[target] = depths[source] + 1
                parents[target] = source, edge
                if target == target_id:
                    found = True
                    break
                queue.append(target)
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        if found:
            current = target_id
            nodes.append(self.nodes[current])
            while current != source_id:
                parent, edge = parents[current]
                edges.append(edge)
                nodes.append(self.nodes[parent])
                current = parent
            nodes.reverse()
            edges.reverse()
        return GraphPath(
            found=found,
            nodes=tuple(nodes),
            edges=tuple(edges),
            visited_nodes=len(depths),
            truncated=truncated,
            generated_at=self.graph.generated_at,
            parser_version=self.graph.parser_version,
        )
