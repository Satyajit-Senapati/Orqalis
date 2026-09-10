import dagre from "@dagrejs/dagre";
import { Position, type Edge, type Node } from "@xyflow/react";

/** Layout only: preserve every runtime node and relationship. */
export function layout(nodes: Node[], edges: Edge[]): Node[] {
  if (!nodes.length) return [];
  const graph = new dagre.graphlib.Graph().setGraph({
    rankdir: "LR",
    nodesep: 32,
    ranksep: 70,
  });
  graph.setDefaultEdgeLabel(() => ({}));
  nodes.forEach((node) => graph.setNode(node.id, { width: 240, height: 100 }));
  edges.forEach((edge) => graph.setEdge(edge.source, edge.target));
  dagre.layout(graph);
  const columns = [...new Set(nodes.map((n) => graph.node(n.id).x))].sort(
    (a, b) => a - b,
  );
  const ys = nodes.map((n) => graph.node(n.id).y);
  const minY = Math.min(...ys),
    spread = Math.max(...ys) - minY;
  // Narrow serial plans otherwise fit as an unreadably small horizontal strip.
  // Keep branching DAGs in their ordinary layered layout.
  const wrap = columns.length >= 6 && spread <= 160;
  return nodes.map((node) => {
    const point = graph.node(node.id);
    const rank = columns.indexOf(point.x),
      row = Math.floor(rank / 4);
    const reverse = wrap && row % 2 === 1;
    return {
      ...node,
      position: wrap
        ? {
            x: (reverse ? 3 - (rank % 4) : rank % 4) * 310,
            y: row * (spread + 170) + point.y - minY,
          }
        : { x: point.x - 120, y: point.y - 50 },
      sourcePosition: reverse ? Position.Left : Position.Right,
      targetPosition: reverse ? Position.Right : Position.Left,
    };
  });
}
