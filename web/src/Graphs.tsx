import { useMemo, useState, useSyncExternalStore } from "react";
import { Background, Controls, MiniMap, ReactFlow, type Edge, type Node } from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import "@xyflow/react/dist/style.css";
import { duration } from "./api";
import { Badge, Empty, label } from "./ui";
import type { Snapshot } from "./types";

export function layout(nodes: Node[], edges: Edge[]): Node[] {
  const graph = new dagre.graphlib.Graph().setGraph({ rankdir: "LR", nodesep: 32, ranksep: 70 });
  graph.setDefaultEdgeLabel(() => ({}));
  nodes.forEach(node => graph.setNode(node.id, { width: 240, height: 100 }));
  edges.forEach(edge => graph.setEdge(edge.source, edge.target));
  dagre.layout(graph);
  return nodes.map(node => ({ ...node, position: {
    x: graph.node(node.id).x - 120, y: graph.node(node.id).y - 50,
  } }));
}
function observeTheme(callback: () => void) {
  const observer = new MutationObserver(callback);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => observer.disconnect();
}
export function FlowGraph({ nodes, edges, onSelect, name }: {
  nodes: Node[]; edges: Edge[]; onSelect?: (id: string) => void; name: string;
}) {
  const theme = useSyncExternalStore(observeTheme, () => document.documentElement.dataset.theme === "light" ? "light" : "dark");
  const placed = useMemo(() => layout(nodes, edges), [nodes, edges]);
  return <div className="flow-canvas" role="region" aria-label={name}>
    <ReactFlow nodes={placed} edges={edges} fitView nodesDraggable={false} nodesConnectable={false}
      deleteKeyCode={null} minZoom={0.08} maxZoom={1.5}
      onNodeClick={(_, node) => onSelect?.(node.id)} colorMode={theme}>
      <Background gap={24} /><Controls showInteractive={false} /><MiniMap pannable zoomable />
    </ReactFlow>
  </div>;
}
export function ExecutionGraph({ snapshot }: { snapshot: Snapshot }) {
  const [mode, setMode] = useState<"tasks" | "actors">("tasks");
  const [selected, setSelected] = useState("");
  const tasks = snapshot.plan?.tasks ?? [];
  const edges: Edge[] = mode === "tasks" ? [
    ...(snapshot.plan?.dependencies ?? []).map(edge => ({
      id: `${edge.depends_on_task_id}-${edge.task_id}`, source: edge.depends_on_task_id, target: edge.task_id,
      type: "smoothstep", className: "dependency-edge",
    })),
    ...tasks.filter(t => t.parent_task_id).map(t => ({
      id: `repair-${t.id}`, source: t.parent_task_id!, target: t.id, label: "repair",
      type: "smoothstep", style: { strokeDasharray: "5 4", stroke: "#d5a95f" },
    })),
  ] : snapshot.actors.filter(a => a.session.actor_type === "AGENT").flatMap(a => {
    const root = snapshot.actors.find(actor => actor.session.actor_type === "ORCHESTRATOR");
    return root ? [{ id: a.session.id, source: root.session.id, target: a.session.id, type: "smoothstep" }] : [];
  });
  const nodes: Node[] = mode === "tasks" ? tasks.map(task => ({
    id: task.id, position: { x: 0, y: 0 }, className: `task-node status-${task.status.toLowerCase()} ${snapshot.statistics.critical_path_task_ids.includes(task.id) ? "critical-node" : ""}`,
    data: { label: <><small>{label(task.preferred_role)}</small><strong>{task.description}</strong>
      <span>{label(task.status)} · {duration(snapshot.task_timing[task.id]?.active_ms ?? 0)}</span></> },
    ariaLabel: `${task.description}, ${task.status}, ${task.preferred_role}`,
  })) : snapshot.actors.map(actor => ({
    id: actor.session.id, position: { x: 0, y: 0 }, className: "task-node",
    data: { label: <><small>{actor.session.actor_type}</small><strong>{label(actor.session.role ?? "Orchestrator")}</strong>
      <span>{label(actor.session.status)} · {duration(actor.timing.wall_ms)}</span></> },
  }));
  const task = tasks.find(t => t.id === selected);
  return <section className="panel operational-panel">
    <div className="section-heading"><h2>Execution graph</h2><div className="segmented">
      <button aria-pressed={mode === "tasks"} onClick={() => setMode("tasks")}>Task DAG</button>
      <button aria-pressed={mode === "actors"} onClick={() => setMode("actors")}>Actor relationships</button>
    </div></div>
    {nodes.length ? <FlowGraph nodes={nodes} edges={edges} name="Execution graph" onSelect={setSelected} /> : <Empty>No runtime graph yet.</Empty>}
    <div className="panel-body graph-note">Solid lines: dependencies. Dashed lines: repair ancestry.
      Outlined tasks: observed critical path, {duration(snapshot.statistics.critical_path_working_ms)} working time.</div>
    <div className="panel-body"><label className="field-label">Inspect task
      <select value={task?.id ?? ""} onChange={e => setSelected(e.target.value)}>
        <option value="">Select a task</option>{tasks.map(t => <option key={t.id} value={t.id}>{t.description}</option>)}
      </select></label>
      {task && <div className="detail-card"><h3>{task.description}</h3><Badge status={task.status} />
        <p>{task.expected_outcome}</p><dl><dt>Capabilities</dt><dd>{task.required_capabilities.join(", ") || "Role capabilities"}</dd>
          <dt>Queue / working / waiting / blocked</dt><dd>{["queue_ms", "active_ms", "waiting_ms", "blocked_ms"].map(key =>
            duration(snapshot.task_timing[task.id]?.[key as keyof typeof snapshot.task_timing[string]] ?? 0)).join(" / ")}</dd>
          <dt>Acceptance affected</dt><dd>{snapshot.goal?.criteria.filter(c => task.acceptance_criterion_ids.includes(c.id)).map(c => c.key).join(", ") || "Delivery contract"}</dd>
          <dt>Attempts</dt><dd>{task.attempt_count}</dd></dl></div>}
    </div>
  </section>;
}
