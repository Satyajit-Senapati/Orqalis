import pytest

from orqalis.domain.errors import InputError, NotFoundError
from orqalis.graph.models import GraphEdge, GraphNode, GraphProvenance, ProjectGraph
from orqalis.graph.queries import GraphQueries


def fixture() -> GraphQueries:
    nodes = tuple(GraphNode(id=n, name=n, kind="FUNCTION", file_path=f"{n}.py") for n in "abcde")
    edges = tuple(
        GraphEdge(
            id=source + target,
            source_id=source,
            target_id=target,
            relation="CALLS",
            provenance=GraphProvenance.INFERRED if source == "d" else GraphProvenance.EXTRACTED,
            confidence=0.6 if source == "d" else 1,
            evidence=(f"{source}.py:2",),
        )
        for source, target in (("a", "b"), ("b", "c"), ("d", "c"), ("c", "a"))
    )
    return GraphQueries(ProjectGraph(parser_version="fixture", nodes=nodes, edges=edges))


def test_impact_walks_incoming_dependencies_with_evidence_and_cycle_control() -> None:
    query = fixture()
    result = query.impact("c.py")
    assert [node.id for node in result.nodes] == ["c", "b", "d", "a"]
    assert result.depths == {"c": 0, "b": 1, "d": 1, "a": 2}
    assert result.edges[1].provenance == GraphProvenance.INFERRED
    assert all(edge.evidence for edge in result.edges)
    assert not result.truncated
    assert "d" not in query.impact("c", include_inferred=False).depths
    assert "d" not in query.impact("c", min_confidence=0.9).depths


def test_graph_limits_report_incomplete_results() -> None:
    query = fixture()
    depth = query.impact("c", max_depth=1)
    assert depth.truncated and "a" not in depth.depths
    limited = query.impact("c", max_nodes=2)
    assert limited.truncated and len(limited.nodes) == 2
    path = query.shortest_path("a", "c", max_depth=1)
    assert not path.found and path.truncated
    path = query.shortest_path("a", "c", max_nodes=2)
    assert not path.found and path.truncated
    missing = query.shortest_path("a", "e")
    assert not missing.found and not missing.truncated


def test_paths_respect_direction_and_provenance() -> None:
    query = fixture()
    directed = query.shortest_path("a", "c")
    assert [node.id for node in directed.nodes] == ["a", "b", "c"]
    assert [edge.id for edge in directed.edges] == ["ab", "bc"]
    both = query.shortest_path("a", "c", direction="both")
    assert [node.id for node in both.nodes] == ["a", "c"]
    assert both.edges[0].source_id == "c"  # Original edge direction remains intact.
    assert not query.shortest_path("d", "c", include_inferred=False).found
    identity = query.shortest_path("a", "a")
    assert identity.found and not identity.edges and identity.visited_nodes == 1


@pytest.mark.parametrize(
    ("depth", "nodes", "confidence"),
    [(0, 100, 0), (21, 100, 0), (3, 0, 0), (3, 1001, 0), (3, 100, -0.1), (3, 100, float("nan"))],
)
def test_graph_invalid_budgets_are_rejected(depth: int, nodes: int, confidence: float) -> None:
    with pytest.raises(InputError):
        fixture().impact("c", max_depth=depth, max_nodes=nodes, min_confidence=confidence)


def test_unknown_nodes_are_not_interpreted_as_filesystem_reads() -> None:
    with pytest.raises(NotFoundError):
        fixture().impact("../../other-project/secret.py")
    with pytest.raises(NotFoundError):
        fixture().shortest_path("missing", "a")
