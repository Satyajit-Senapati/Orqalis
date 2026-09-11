import { useEffect, useState } from "react";
import { duration, get } from "./api";
import { Badge, count, Empty, label } from "./ui";
import type { Run, Snapshot } from "./types";

export function MetricsView({
  snapshot,
  runs,
}: {
  snapshot: Snapshot;
  runs: Run[];
}) {
  const stats = snapshot.statistics;
  const [selected, setSelected] = useState("");
  const actor =
    snapshot.actors.find((a) => a.session.id === selected) ??
    snapshot.actors[0];
  const attempts = snapshot.attempts.filter(
    (a) => a.assigned_actor_session_id === actor?.session.id,
  );
  const calls = snapshot.providers.filter(
    (p) => p.actor_session_id === actor?.session.id,
  );
  const tools = snapshot.tools.filter(
    (t) => t.actor_session_id === actor?.session.id,
  );
  const artifacts = snapshot.artifacts.filter((a) =>
    attempts.some((attempt) => attempt.task_id === a.task_id),
  );
  return (
    <div className="operational-stack">
      <section className="panel operational-panel">
        <div className="section-heading">
          <h2>Runtime statistics</h2>
          <span>Reported telemetry</span>
        </div>
        <div className="stat-grid">
          {[
            ["Input tokens", count(stats.reported_input_tokens)],
            ["Output tokens", count(stats.reported_output_tokens)],
            ["Cached input tokens", count(stats.reported_cached_tokens)],
            [
              "Reported cost",
              stats.reported_cost_usd == null
                ? "Not reported"
                : `$${stats.reported_cost_usd.toFixed(4)}`,
            ],
            ["Provider calls", String(stats.provider_calls)],
            ["Tool calls", String(stats.tool_calls)],
            [
              "First-pass success",
              stats.first_pass_success == null
                ? "Not reviewed"
                : stats.first_pass_success
                  ? "Yes"
                  : "No",
            ],
            ["Repair iterations", String(snapshot.run.repair_iteration)],
          ].map(([name, value]) => (
            <div key={name}>
              <span>{name}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
        <p className="panel-body">
          Token coverage: {stats.calls_with_usage}/{stats.provider_calls} calls.
          Cost coverage: {stats.calls_with_cost}/{stats.provider_calls} calls.
          Unknown usage stays unknown.
        </p>
        <div className="panel-body phase-chart">
          <h3>Phase working time</h3>
          {snapshot.phases.map((phase) => (
            <div className="phase-chart-row" key={phase.execution.id}>
              <span>
                {label(phase.execution.phase)} · {phase.execution.iteration}
              </span>
              <div>
                <i
                  style={{
                    width: `${(phase.timing.active_ms / Math.max(1, ...snapshot.phases.map((p) => p.timing.wall_ms))) * 100}%`,
                  }}
                />
              </div>
              <b>{duration(phase.timing.active_ms)}</b>
            </div>
          ))}
        </div>
      </section>
      <section className="panel operational-panel">
        <div className="section-heading">
          <h2>Actor detail</h2>
          <label>
            Actor{" "}
            <select
              aria-label="Actor"
              value={actor?.session.id ?? ""}
              onChange={(e) => setSelected(e.target.value)}
            >
              {snapshot.actors.map((a) => (
                <option key={a.session.id} value={a.session.id}>
                  {label(a.session.role ?? "Orchestrator")} ·{" "}
                  {a.session.id.slice(0, 8)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {!actor ? (
          <Empty>No actors instantiated.</Empty>
        ) : (
          <div className="panel-body">
            <h3>
              {label(actor.session.role ?? "Orchestrator")}{" "}
              <Badge status={actor.session.status} />
            </h3>
            <dl>
              <dt>Provider / model</dt>
              <dd>
                {actor.session.provider ?? "Core runtime"} /{" "}
                {actor.session.model ?? "Not applicable"}
              </dd>
              <dt>Working / waiting / blocked</dt>
              <dd>
                {duration(actor.timing.active_ms)} /{" "}
                {duration(actor.timing.waiting_ms)} /{" "}
                {duration(actor.timing.blocked_ms)}
              </dd>
              <dt>Working share of session</dt>
              <dd>
                {actor.timing.wall_ms
                  ? (
                      (actor.timing.active_ms / actor.timing.wall_ms) *
                      100
                    ).toFixed(1)
                  : "0"}
                %
              </dd>
              <dt>Attempts / complete / failed</dt>
              <dd>
                {actor.session.tasks_attempted} /{" "}
                {actor.session.tasks_completed} / {actor.session.tasks_failed}
              </dd>
              <dt>Started / completed</dt>
              <dd>
                {new Date(actor.session.started_at).toLocaleString()} /{" "}
                {actor.session.completed_at
                  ? new Date(actor.session.completed_at).toLocaleString()
                  : "Active session"}
              </dd>
              <dt>Loaded skills</dt>
              <dd>
                {actor.session.loaded_skills.join(", ") ||
                  "No dynamic skills required"}
              </dd>
              <dt>Allowed tools</dt>
              <dd>
                {actor.session.allowed_tools.join(", ") ||
                  "Core service operations"}
              </dd>
            </dl>
            <h3>Task history</h3>
            {attempts.map((attempt) => (
              <p className="history-line" key={attempt.id}>
                {
                  snapshot.tasks.find((t) => t.id === attempt.task_id)
                    ?.description
                }{" "}
                · attempt {attempt.attempt} <Badge status={attempt.status} />
              </p>
            ))}
            <h3>Files and artifacts</h3>
            {artifacts.length ? (
              artifacts.map((a) => (
                <p className="history-line" key={a.id}>
                  {a.path_or_uri}
                </p>
              ))
            ) : (
              <p>No artifacts attributed to this actor.</p>
            )}
            <h3>Provider activity</h3>
            {calls.length ? (
              calls.map((call) => (
                <details className="detail-card" key={call.id}>
                  <summary>
                    {call.provider} / {call.model}{" "}
                    <Badge status={call.status} />
                  </summary>
                  <dl>
                    <dt>Started</dt>
                    <dd>{new Date(call.started_at).toLocaleString()}</dd>
                    <dt>Input / output / cached</dt>
                    <dd>
                      {count(call.usage?.input_tokens)} /{" "}
                      {count(call.usage?.output_tokens)} /{" "}
                      {count(call.usage?.cached_input_tokens)}
                    </dd>
                    <dt>Error</dt>
                    <dd>{call.error_code ?? "None"}</dd>
                  </dl>
                </details>
              ))
            ) : (
              <p>No provider calls attributed to this actor.</p>
            )}
            <h3>Tool activity</h3>
            {tools.map((tool) => (
              <details className="detail-card" key={tool.id}>
                <summary>
                  {tool.tool} <Badge status={tool.status} />
                </summary>
                <pre>{tool.observation?.summary ?? "Awaiting result"}</pre>
              </details>
            ))}
          </div>
        )}
      </section>
      <RunComparison current={snapshot} runs={runs} />
    </div>
  );
}

type ComparisonRequest =
  | { id: ""; status: "idle" }
  | { id: string; status: "loading" }
  | { id: string; status: "success"; value: Snapshot }
  | { id: string; status: "error"; message: string };

function RunComparison({ current, runs }: { current: Snapshot; runs: Run[] }) {
  const candidates = runs.filter(
    (run) =>
      run.id !== current.run.id && run.project_id === current.run.project_id,
  );
  const [selection, setSelection] = useState({
    projectId: current.run.project_id,
    runId: "",
  });
  const [requestAttempt, setRequestAttempt] = useState(0);
  const [request, setRequest] = useState<ComparisonRequest>({
    id: "",
    status: "idle",
  });
  const selected =
    selection.projectId === current.run.project_id &&
    candidates.some((candidate) => candidate.id === selection.runId)
      ? selection.runId
      : "";
  const requestId = selected
    ? JSON.stringify([current.run.id, selected, requestAttempt])
    : "";
  const currentRequest: ComparisonRequest = !selected
    ? { id: "", status: "idle" }
    : request.id === requestId
      ? request
      : { id: requestId, status: "loading" };
  const loading = currentRequest.status === "loading";
  const other =
    currentRequest.status === "success" ? currentRequest.value : null;
  const error = currentRequest.status === "error" ? currentRequest.message : "";

  useEffect(() => {
    if (!selected) return;
    const abort = new AbortController();
    get<Snapshot>(`/api/runs/${selected}`, abort.signal)
      .then((value) => {
        if (!abort.signal.aborted) {
          setRequest({
            id: requestId,
            status: "success",
            value,
          });
        }
      })
      .catch((failure: unknown) => {
        if (!abort.signal.aborted) {
          setRequest({
            id: requestId,
            status: "error",
            message: String(failure),
          });
        }
      });
    return () => abort.abort();
  }, [requestId, selected]);

  return (
    <section
      className="panel operational-panel"
      aria-busy={loading}
      aria-label="Compare historical runs"
    >
      <div className="section-heading">
        <h2>Compare historical runs</h2>
      </div>
      <div className="panel-body">
        <label className="field-label">
          Comparison run
          <select
            aria-label="Comparison run"
            value={selected}
            onChange={(event) => {
              setSelection({
                projectId: current.run.project_id,
                runId: event.target.value,
              });
              setRequestAttempt((attempt) => attempt + 1);
            }}
          >
            <option value="">Select a run</option>
            {candidates.map((run) => (
              <option key={run.id} value={run.id}>
                {run.request} · {run.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </label>
        {error && (
          <div role="alert">
            <p>{error}</p>
            <button
              type="button"
              onClick={() => setRequestAttempt((attempt) => attempt + 1)}
            >
              Retry comparison
            </button>
          </div>
        )}
      </div>
      {loading ? (
        <Empty>Loading persisted comparison…</Empty>
      ) : error ? null : selected && other ? (
        <div className="table-scroll">
          <table>
            <caption className="sr-only">Persisted run comparison</caption>
            <thead>
              <tr>
                <th>Metric</th>
                <th>This run</th>
                <th>{other.run.id.slice(0, 8)}</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Status", current.run.state, other.run.state],
                [
                  "Elapsed",
                  duration(current.timing.wall_ms),
                  duration(other.timing.wall_ms),
                ],
                [
                  "Working",
                  duration(current.timing.active_ms),
                  duration(other.timing.active_ms),
                ],
                [
                  "Waiting",
                  duration(current.timing.waiting_ms),
                  duration(other.timing.waiting_ms),
                ],
                [
                  "Blocked",
                  duration(current.timing.blocked_ms),
                  duration(other.timing.blocked_ms),
                ],
                [
                  "Repairs",
                  current.run.repair_iteration,
                  other.run.repair_iteration,
                ],
                [
                  "Provider calls",
                  current.statistics.provider_calls,
                  other.statistics.provider_calls,
                ],
                [
                  "Input tokens",
                  count(current.statistics.reported_input_tokens),
                  count(other.statistics.reported_input_tokens),
                ],
              ].map(([name, left, right]) => (
                <tr key={name}>
                  <th>{name}</th>
                  <td>{left}</td>
                  <td>{right}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty>
          {candidates.length
            ? "Select another run in this project to compare persisted results."
            : "No other runs in this project are available for comparison."}
        </Empty>
      )}
    </section>
  );
}
