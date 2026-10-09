import { useState } from "react";
import { duration } from "./api";
import type { Snapshot, TraceNode } from "./types";
import { Badge, Empty, label } from "./ui";

export function TraceView({ snapshot }: { snapshot: Snapshot }) {
  const [kind, setKind] = useState<"all" | TraceNode["kind"]>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const nodes = snapshot.trace ?? [];
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const filtered = nodes.filter((node) => kind === "all" || node.kind === kind);
  const currentPage = Math.min(page, Math.max(0, Math.ceil(filtered.length / 50) - 1));
  const visible = filtered.slice(currentPage * 50, (currentPage + 1) * 50);
  const selected = selectedId ? byId.get(selectedId) : undefined;
  const ancestry: TraceNode[] = [];
  const seen = new Set<string>();
  let ancestor = selected;
  while (ancestor && !seen.has(ancestor.id)) {
    seen.add(ancestor.id);
    ancestry.unshift(ancestor);
    ancestor = ancestor.parent_id ? byId.get(ancestor.parent_id) : undefined;
  }
  const provider = snapshot.providers.find((call) => call.id === selected?.provider_invocation_id);
  const evidence = selected?.task_execution_id
    ? snapshot.evidence.filter((item) => item.task_execution_id === selected.task_execution_id)
    : [];

  function choose(id: string) {
    setSelectedId(id);
  }

  return <section className="panel operational-panel" aria-label="Local operation trace">
    <div className="section-heading">
      <h2>Operation trace</h2>
      <label>Show <select aria-label="Trace operation type" value={kind} onChange={(event) => {
        setKind(event.target.value as typeof kind); setPage(0); setSelectedId(null);
      }}>
        <option value="all">All operations</option>
        {(["run", "phase", "task", "actor", "model", "tool"] as const).map((value) =>
          <option key={value} value={value}>{label(value)}</option>)}
      </select></label>
    </div>
    <p className="panel-body">Persisted operation identities link phases, task attempts, agent sessions, model calls, and tools. Shared sessions retain links to each attempt.</p>
    {!nodes.length ? <Empty>No correlated operations recorded in this snapshot.</Empty> : <div className="table-scroll">
      <table><caption className="sr-only">Local operation hierarchy</caption>
        <thead><tr><th>Operation</th><th>Parent</th><th>Status</th><th>Completed duration</th></tr></thead>
        <tbody>{visible.map((node) => <tr key={node.id}>
          <td><button type="button" aria-pressed={selectedId === node.id} onClick={() => choose(node.id)}>{label(node.kind)}: {node.label} / {node.entity_id.slice(0, 8)}</button></td>
          <td>{node.parent_id && byId.has(node.parent_id) ? <button type="button" onClick={() => choose(node.parent_id!)}>{byId.get(node.parent_id)!.label} / {byId.get(node.parent_id)!.entity_id.slice(0, 8)}</button> : "Root"}</td>
          <td><Badge status={node.status} /></td>
          <td>{node.duration_ms == null ? "Not reported" : duration(node.duration_ms)}</td>
        </tr>)}</tbody>
      </table>
    </div>}
    {filtered.length > 50 && <div className="panel-body view-toolbar">
      <button disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>Previous operations</button>
      <span>{currentPage * 50 + 1} - {Math.min((currentPage + 1) * 50, filtered.length)} of {filtered.length}</span>
      <button disabled={(currentPage + 1) * 50 >= filtered.length} onClick={() => setPage(currentPage + 1)}>Next operations</button>
    </div>}
    {selected && <div className="panel-body detail-card" aria-live="polite">
      <h3>{selected.label}</h3>
      <nav aria-label="Operation ancestry">{ancestry.map((node) => <button key={node.id} type="button" onClick={() => choose(node.id)}>{node.label}</button>)}</nav>
      <dl>
        <dt>Identity</dt><dd>{selected.id}</dd>
        <dt>Start / completion</dt><dd>{selected.started_at ?? "Not reported"} / {selected.completed_at ?? "Not reported"}</dd>
        <dt>Task</dt><dd>{snapshot.tasks.find((task) => task.id === selected.task_id)?.description ?? "No task attributed"}</dd>
        <dt>Task attempt</dt><dd>{selected.task_execution_id ?? "Not attributed"}</dd>
        <dt>Agent session</dt><dd>{selected.actor_session_id ?? "Not attributed"}</dd>
        <dt>Provider / model</dt><dd>{provider ? `${provider.provider} / ${provider.model}` : "Not attributed"}</dd>
        <dt>Evidence for this task attempt</dt><dd>{evidence.map((item) => item.id).join(", ") || "No evidence attributed"}</dd>
        <dt>Related operations</dt><dd>{selected.related_ids.length ? selected.related_ids.map((id) => <button type="button" key={id} onClick={() => choose(id)}>{byId.get(id)?.label ?? id}</button>) : "None recorded"}</dd>
      </dl>
    </div>}
  </section>;
}
