import { useEffect, useState } from "react";
import { get } from "./api";
import { FlowGraph } from "./Graphs";
import { Badge, Empty, label } from "./ui";
import type { Brain, Snapshot } from "./types";

export function BrainView({ snapshot }: { snapshot: Snapshot }) {
  const [brain, setBrain] = useState<Brain | null>(null);
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [category, setCategory] = useState("");
  const [error, setError] = useState("");
  const [graph, setGraph] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    get<Brain>(`/api/projects/${snapshot.run.project_id}/brain?run_id=${snapshot.run.id}&query=${encodeURIComponent(submitted)}`, controller.signal)
      .then(result => { setBrain(result); setError(""); })
      .catch((failure: unknown) => { if (!controller.signal.aborted) setError(String(failure)); });
    return () => controller.abort();
  }, [snapshot.run.project_id, snapshot.run.id, submitted]);
  const matches = brain?.matches.filter(m => !category || m.item.type === category) ?? [];
  const entities = brain?.entities.slice(0, 150) ?? [];
  const ids = new Set(entities.map(e => e.id));
  return <section className="panel operational-panel">
    <div className="section-heading"><h2>Project Brain</h2>{brain && <Badge status={brain.freshness.fresh ? "PASS" : "STALE"} />}</div>
    <div className="panel-body"><form className="search-form" onSubmit={event => { event.preventDefault(); setSubmitted(query); }}>
      <label className="field-label">Search project knowledge<input value={query} onChange={e => setQuery(e.target.value)} placeholder="Architecture, conventions, decisions…" /></label>
      <button type="submit">Search</button></form>
      {error && <p role="alert">{error}</p>}
      {brain && <><dl className="brain-health"><dt>Indexed commit</dt><dd><code>{brain.freshness.indexed_commit ?? "Not indexed"}</code></dd>
        <dt>Inspected HEAD</dt><dd><code>{brain.freshness.current_commit}</code></dd><dt>Workspace</dt><dd>{brain.inspected_root}</dd>
        <dt>Active facts</dt><dd>{brain.freshness.active_items}</dd><dt>Uncommitted paths</dt><dd>{brain.freshness.dirty_paths.join(", ") || "None"}</dd></dl>
        <div className="view-toolbar"><label>Category <select value={category} onChange={e => setCategory(e.target.value)}><option value="">All categories</option>
          {[...new Set(brain.matches.map(m => m.item.type))].sort().map(type => <option key={type} value={type}>{label(type)}</option>)}</select></label>
          <button aria-pressed={graph} onClick={() => setGraph(!graph)}>Knowledge graph</button></div></>}
    </div>
    {graph && brain && <><FlowGraph name="Project knowledge graph"
      nodes={entities.map(entity => ({ id: entity.id, position: { x: 0, y: 0 }, data: { label: entity.name }, className: "task-node" }))}
      edges={brain.relations.filter(r => ids.has(r.source_entity_id) && ids.has(r.target_entity_id)).map(r => ({
        id: r.id, source: r.source_entity_id, target: r.target_entity_id, label: r.relation_type, type: "smoothstep",
      }))} /><p className="panel-body">Showing {entities.length} of {brain.entities.length} source-backed entities.</p></>}
    {!brain ? <Empty>Retrieving committed knowledge…</Empty> : !matches.length ? <Empty>No matching knowledge. Try a different query.</Empty> :
      <div className="memory-grid">{matches.map(({ item, sources }) => <article className="memory-card" key={item.id}>
        <div><span className="eyebrow">{label(item.type)}</span><span>{Math.round(item.confidence * 100)}% confidence</span></div>
        <h3>{item.title}</h3><pre>{item.content}</pre>
        <dl><dt>Source commit</dt><dd><code>{item.source_commit}</code></dd><dt>Verified</dt><dd>{new Date(item.last_verified_at).toLocaleString()}</dd>
          <dt>Sources</dt><dd>{sources.map(source => <p key={source.source_ref}>{source.source_ref}</p>)}</dd></dl>
        {item.introduced_by_run && <a className="text-link" href={`/runs/${item.introduced_by_run}`}>Originating run {item.introduced_by_run.slice(0, 8)} ↗</a>}
      </article>)}</div>}
  </section>;
}
