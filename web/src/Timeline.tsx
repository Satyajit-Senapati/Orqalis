import { useState } from "react";
import { duration } from "./api";
import { Empty, label } from "./ui";
import type { Segment, Snapshot } from "./types";

export function Timeline({ snapshot }: { snapshot: Snapshot }) {
  const [kind, setKind] = useState<"all" | Segment["kind"]>("all");
  const [selected, setSelected] = useState<Segment | null>(null);
  const segments = snapshot.timeline.filter(
    (s) => kind === "all" || s.kind === kind,
  );
  const grouped = new Map<string, Segment[]>();
  for (const segment of segments) {
    const key = segment.kind + ":" + segment.entity_id;
    const parts = grouped.get(key) ?? [];
    parts.push(segment);
    grouped.set(key, parts);
  }
  const [page, setPage] = useState(0);
  const allRows = [...grouped.keys()];
  const currentPage = Math.min(
    page,
    Math.max(0, Math.ceil(allRows.length / 50) - 1),
  );
  const rows = allRows.slice(currentPage * 50, (currentPage + 1) * 50);
  const start = Math.min(
    ...snapshot.timeline.map((s) => Date.parse(s.started_at)),
  );
  const end = Math.max(...snapshot.timeline.map((s) => Date.parse(s.ended_at)));
  const span = Math.max(1, end - start);
  function title(segment: Segment) {
    if (segment.kind === "actor") {
      const actor = snapshot.actors.find(
        (a) => a.session.id === segment.entity_id,
      );
      return actor?.session.actor_type === "ORCHESTRATOR"
        ? "Orchestrator"
        : label(actor?.session.role ?? "agent");
    }
    if (segment.kind === "phase") {
      const phase = snapshot.phases.find(
        (p) => p.execution.id === segment.entity_id,
      )?.execution;
      return `${label(phase?.phase ?? "phase")} · ${phase?.iteration ?? 1}`;
    }
    const attempt = snapshot.attempts.find((a) => a.id === segment.entity_id);
    return `${snapshot.tasks.find((t) => t.id === segment.task_id)?.description ?? "Task"} · attempt ${attempt?.attempt ?? 1}`;
  }
  return (
    <section className="panel operational-panel">
      <div className="section-heading">
        <h2>Execution timeline</h2>
        <label>
          Show{" "}
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as typeof kind)}
          >
            <option value="all">All tracks</option>
            <option value="actor">Actors</option>
            <option value="task">Tasks</option>
            <option value="phase">Phases</option>
          </select>
        </label>
      </div>
      <div className="panel-body timeline-summary">
        <span>
          Peak task parallelism <b>{snapshot.statistics.max_parallel_tasks}</b>
        </span>
        <span>
          Mean task parallelism{" "}
          <b>{snapshot.statistics.mean_parallel_tasks.toFixed(2)}</b>
        </span>
        <span>Measured working time, not a completion forecast</span>
      </div>
      {!rows.length ? (
        <Empty>No persisted execution intervals yet.</Empty>
      ) : (
        <div className="timeline-scroll">
          <div className="timeline-axis">
            <span>Track</span>
            <div>
              {[0, 0.25, 0.5, 0.75, 1].map((fraction) => (
                <time key={fraction} style={{ left: `${fraction * 100}%` }}>
                  {new Date(start + span * fraction).toLocaleTimeString()}
                </time>
              ))}
            </div>
          </div>
          {rows.map((row) => {
            const parts = grouped.get(row)!;
            return (
              <div className="timeline-row" key={row}>
                <div>
                  <small>{parts[0].kind}</small>
                  <strong title={title(parts[0])}>{title(parts[0])}</strong>
                </div>
                <div className="timeline-track">
                  {parts.map((part, index) => (
                    <div
                      key={index}
                      tabIndex={0}
                      role="button"
                      onClick={() => setSelected(part)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelected(part);
                        }
                      }}
                      aria-label={`${title(part)}: ${label(part.status)}, ${part.duration_ms} milliseconds, ${part.started_at} to ${part.ended_at}`}
                      title={`${label(part.status)} · ${duration(part.duration_ms)} (${part.duration_ms} ms)`}
                      className={`timeline-bar status-${part.status.toLowerCase()}`}
                      style={{
                        left: `${((Date.parse(part.started_at) - start) / span) * 100}%`,
                        width: `${(part.duration_ms / span) * 100}%`,
                      }}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
      {allRows.length > 50 && (
        <div className="panel-body view-toolbar">
          <button
            disabled={currentPage === 0}
            onClick={() => setPage(currentPage - 1)}
          >
            Previous tracks
          </button>
          <span>
            Tracks {currentPage * 50 + 1}–
            {Math.min((currentPage + 1) * 50, allRows.length)} of{" "}
            {allRows.length}
          </span>
          <button
            disabled={(currentPage + 1) * 50 >= allRows.length}
            onClick={() => setPage(currentPage + 1)}
          >
            Next tracks
          </button>
        </div>
      )}
      {selected && (
        <div className="panel-body detail-card">
          <h3>{title(selected)}</h3>
          <dl>
            <dt>Status</dt>
            <dd>{label(selected.status)}</dd>
            <dt>Start</dt>
            <dd>{selected.started_at}</dd>
            <dt>End</dt>
            <dd>{selected.ended_at}</dd>
            <dt>Duration</dt>
            <dd>{selected.duration_ms} ms</dd>
            <dt>Task evidence</dt>
            <dd>
              {snapshot.evidence
                .filter(
                  (e) =>
                    e.task_execution_id === selected.entity_id ||
                    (selected.task_id && e.task_id === selected.task_id),
                )
                .map((e) => e.id)
                .join(", ") || "No evidence attributed to this interval"}
            </dd>
          </dl>
        </div>
      )}
      <div className="panel-body legend">
        <span>
          <i className="green" />
          Working
        </span>
        <span>
          <i className="amber" />
          Waiting
        </span>
        <span>
          <i className="rose" />
          Blocked
        </span>
        <span>
          Intervals are reconstructed by Orqalis Core from persisted events.
        </span>
      </div>
    </section>
  );
}
