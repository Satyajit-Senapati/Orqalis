import { useMemo, useState, useSyncExternalStore } from "react";
import {
  Background,
  Controls,
  MiniMap,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import { layout } from "./graph-layout";
import "@xyflow/react/dist/style.css";
import { duration } from "./api";
import { classToken, Empty, label } from "./ui";
import type { Snapshot } from "./types";
import { actorName, visibleTasks, type Inspect } from "./runtime";

function observeTheme(callback: () => void) {
  const observer = new MutationObserver(callback);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });
  return () => observer.disconnect();
}
export function FlowGraph({
  nodes,
  edges,
  onSelect,
  name,
}: {
  nodes: Node[];
  edges: Edge[];
  onSelect?: (id: string) => void;
  name: string;
}) {
  const theme = useSyncExternalStore(observeTheme, () =>
    document.documentElement.dataset.theme === "light" ? "light" : "dark",
  );
  const topology = JSON.stringify({
    ids: nodes.map((n) => n.id),
    links: edges.map((e) => [e.source, e.target]),
  });
  const positions = useMemo(() => {
    const model = JSON.parse(topology) as {
      ids: string[];
      links: [string, string][];
    };
    const result = layout(
      model.ids.map((id) => ({ id, data: {}, position: { x: 0, y: 0 } })),
      model.links.map(([source, target], index) => ({
        id: String(index),
        source,
        target,
      })),
    );
    return new Map(
      result.map((n) => [
        n.id,
        {
          position: n.position,
          sourcePosition: n.sourcePosition,
          targetPosition: n.targetPosition,
        },
      ]),
    );
  }, [topology]);
  const placed = nodes.map((n) => ({
    ...n,
    ...positions.get(n.id),
  }));
  return (
    <div className="flow-canvas" role="region" aria-label={name}>
      <ReactFlow
        nodes={placed}
        edges={edges.map((edge) => ({
          ...edge,
          markerEnd: edge.markerEnd ?? { type: MarkerType.ArrowClosed },
        }))}
        fitView
        fitViewOptions={{ padding: 0.07 }}
        nodesDraggable={false}
        nodesConnectable={false}
        deleteKeyCode={null}
        minZoom={0.08}
        maxZoom={1.5}
        onNodeClick={(_, node) => onSelect?.(node.id)}
        colorMode={theme}
      >
        <Background gap={24} />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </div>
  );
}
export function ExecutionGraph({
  snapshot,
  inspect,
  initialMode = "tasks",
}: {
  snapshot: Snapshot;
  inspect: Inspect;
  initialMode?: "tasks" | "actors" | "orchestration";
}) {
  const [mode, setMode] = useState(initialMode);
  const tasks = visibleTasks(snapshot);
  const root = snapshot.actors.find(
    (a) => a.session.actor_type === "ORCHESTRATOR",
  );
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  if (mode !== "tasks") {
    for (const actor of snapshot.actors) {
      nodes.push({
        id: "actor:" + actor.session.id,
        position: { x: 0, y: 0 },
        className: [
          "task-node",
          "actor-node",
          "actor-" + actor.session.actor_type.toLowerCase(),
          "role-" + classToken(actor.session.role ?? actor.session.actor_type),
          "status-" + actor.session.status.toLowerCase(),
        ].join(" "),
        data: {
          label: (
            <>
              <small>
                {actor.session.actor_type === "ORCHESTRATOR"
                  ? "Workflow controller"
                  : "Agent"}
              </small>
              <strong>{actorName(actor)}</strong>
              <span>
                {label(actor.session.status)} · {duration(actor.timing.wall_ms)}
              </span>
            </>
          ),
        },
        ariaLabel: actorName(actor) + ", " + actor.session.status,
      });
      if (root && actor !== root)
        edges.push({
          id: "delegate:" + actor.session.id,
          source: "actor:" + root.session.id,
          target: "actor:" + actor.session.id,
          type: "smoothstep",
          label: "delegates",
          className: "delegation-edge",
        });
    }
  }
  if (mode !== "actors") {
    for (const task of tasks) {
      nodes.push({
        id: "task:" + task.id,
        position: { x: 0, y: 0 },
        className: [
          "task-node",
          "role-" + classToken(task.preferred_role),
          "status-" + task.status.toLowerCase(),
        ].join(" "),
        data: {
          label: (
            <>
              <small>
                {label(task.preferred_role)}
                {task.parent_task_id ? " · repair" : ""}
              </small>
              <strong>{task.description}</strong>
              <span>
                {label(task.status)} ·{" "}
                {duration(snapshot.task_timing[task.id]?.active_ms ?? 0)}
              </span>
            </>
          ),
        },
        ariaLabel:
          task.description + ", " + task.status + ", " + task.preferred_role,
      });
      if (mode === "orchestration") {
        const attempt = snapshot.attempts
          .filter((a) => a.task_id === task.id)
          .at(-1);
        const owner = snapshot.actors.find(
          (a) => a.session.id === attempt?.assigned_actor_session_id,
        );
        if (owner)
          edges.push({
            id: "owns:" + task.id,
            source: "actor:" + owner.session.id,
            target: "task:" + task.id,
            label: "assigned",
            type: "smoothstep",
            className: "assignment-edge",
          });
      }
      if (task.parent_task_id)
        edges.push({
          id: "repair:" + task.id,
          source: "task:" + task.parent_task_id,
          target: "task:" + task.id,
          label: "repair",
          type: "smoothstep",
          className: "repair-edge",
        });
    }
    edges.push(
      ...(snapshot.plan?.dependencies ?? []).map((e) => ({
        id: "depends:" + e.depends_on_task_id + ":" + e.task_id,
        source: "task:" + e.depends_on_task_id,
        target: "task:" + e.task_id,
        type: "smoothstep",
        className: "dependency-edge",
      })),
    );
  }
  const shown = nodes.slice(0, 150),
    ids = new Set(shown.map((n) => n.id));
  function select(id: string) {
    const [kind, record] = id.split(":");
    if ((kind === "actor" || kind === "task") && record)
      inspect({ kind, id: record });
  }
  return (
    <section className="panel operational-panel orchestration-panel">
      <div className="section-heading">
        <div>
          <h2>Execution graph</h2>
          <span>
            {mode === "orchestration"
              ? "Delegation, ownership and dependencies"
              : mode === "actors"
                ? "Instantiated runtime actors"
                : "Dependency-aware task plan"}
          </span>
        </div>
        <div className="segmented">
          <button
            aria-pressed={mode === "orchestration"}
            onClick={() => setMode("orchestration")}
          >
            Orchestration
          </button>
          <button
            aria-pressed={mode === "tasks"}
            onClick={() => setMode("tasks")}
          >
            Task DAG
          </button>
          <button
            aria-pressed={mode === "actors"}
            onClick={() => setMode("actors")}
          >
            Actors
          </button>
        </div>
      </div>
      {shown.length ? (
        <FlowGraph
          nodes={shown}
          edges={edges.filter((e) => ids.has(e.source) && ids.has(e.target))}
          name="Execution graph"
          onSelect={select}
        />
      ) : (
        <Empty>The graph appears when Core records actors or a plan.</Empty>
      )}
      <div className="graph-toolbar">
        <p>
          Solid: dependencies · Dotted: delegation · Dashed: repair
          {nodes.length > shown.length
            ? " · Showing first 150 nodes; all tasks remain in Tasks."
            : ""}
        </p>
        <label className="compact-field">
          Inspect task
          <select
            value=""
            onChange={(e) => {
              if (e.target.value) select("task:" + e.target.value);
            }}
          >
            <option value="">Choose task…</option>
            {tasks.map((t) => (
              <option key={t.id} value={t.id}>
                {t.description}
              </option>
            ))}
          </select>
        </label>
        <label className="compact-field">
          Inspect actor
          <select
            value=""
            onChange={(e) => {
              if (e.target.value) select("actor:" + e.target.value);
            }}
          >
            <option value="">Choose actor…</option>
            {snapshot.actors.map((a) => (
              <option key={a.session.id} value={a.session.id}>
                {actorName(a)}
              </option>
            ))}
          </select>
        </label>
      </div>
    </section>
  );
}
