import { duration } from "./api";
import { Badge, Empty, label } from "./ui";
import type { Snapshot } from "./types";

export function EvidenceView({ snapshot }: { snapshot: Snapshot }) {
  const criteria = snapshot.goal?.criteria ?? [];
  const latest = snapshot.reviews.at(-1);
  return <section className="panel operational-panel">
    <div className="section-heading"><h2>Acceptance evidence</h2><span>Goal version {snapshot.goal?.goal.version ?? "—"}</span></div>
    {snapshot.goal && <details className="panel-body"><summary>Scope, constraints and definition of done</summary>
      {(["scope", "constraints", "definition_of_done"] as const).map(key => <div key={key}><h3>{label(key)}</h3>
        <ul>{snapshot.goal!.goal[key].map(text => <li key={text}>{text}</li>)}</ul></div>)}</details>}
    {!criteria.length && <Empty>No acceptance contract yet.</Empty>}
    {criteria.map(criterion => {
      const evidence = snapshot.evidence.filter(item => item.criterion_id === criterion.id);
      const review = latest?.result.criteria.find(c => c.criterion_id === criterion.id);
      const tasks = snapshot.plan?.tasks.filter(t => t.acceptance_criterion_ids.includes(criterion.id)) ?? [];
      return <details className="evidence-criterion" key={criterion.id} open={criterion.status === "FAIL"}>
        <summary><strong>{criterion.key} · {criterion.description}</strong><Badge status={criterion.status} /></summary>
        <div className="detail-card"><dl><dt>Validation mechanism</dt><dd>{label(criterion.validation_spec.kind)}</dd>
          <dt>Priority</dt><dd>{criterion.priority}</dd><dt>Attempts</dt><dd>{criterion.attempt_count}</dd>
          <dt>Reviewer result</dt><dd>{review ? `${review.status}: ${review.reason}` : "Awaiting independent review"}</dd>
          <dt>Related tasks</dt><dd>{tasks.map(t => <p key={t.id}>{t.parent_task_id ? "Repair: " : ""}{t.description} · {label(t.status)}</p>)}</dd></dl>
          <pre>{JSON.stringify(criterion.validation_spec, null, 2)}</pre>
          {evidence.length ? evidence.map(item => <details key={item.id} className="evidence-record">
            <summary><Badge status={item.structured_data.passed ? "PASS" : "FAIL"} /><span>{label(item.evidence_type)} · {new Date(item.created_at).toLocaleString()}</span></summary>
            <dl><dt>Evidence</dt><dd><code>{item.id}</code></dd><dt>Exit / duration</dt>
              <dd>{item.structured_data.exit_code ?? "Not applicable"} / {duration(item.structured_data.duration_ms)}</dd>
              <dt>Source</dt><dd>{item.structured_data.source_ref ?? "Command result"}</dd>
              <dt>Hash</dt><dd><code>{item.structured_data.content_hash ?? "Not reported"}</code></dd></dl>
            {item.structured_data.error_code && <p role="note">{item.structured_data.error_code}</p>}
            <pre>{item.structured_data.output || "No text output; see structured result."}</pre>
          </details>) : <Empty>No evidence recorded for this criterion.</Empty>}
        </div>
      </details>;
    })}
    <details className="panel-body"><summary>Review history · {snapshot.reviews.length} reviews</summary>
      {snapshot.reviews.map(review => <article className="detail-card" key={review.id}><Badge status={review.result.overall} />
        <span> Plan {review.plan_version} · {new Date(review.created_at).toLocaleString()}</span>
        <ul>{[...review.result.blocking_findings, ...review.result.non_blocking_findings].map((finding, i) => <li key={i}>{finding}</li>)}</ul>
      </article>)}</details>
  </section>;
}
