import { useEffect, useState } from "react";
import { WorkspaceViews } from "./WorkspaceViews";
import { ThemeControl, RunControls } from "./Controls";
import { duration, get, useRun } from "./api";
import type { Project, Run } from "./types";

import { Badge, label, statusTone } from "./ui";
import { retryCount, visibleTasks } from "./runtime";
const phases = [
  "CONTEXT",
  "GOAL",
  "PLAN",
  "IMPLEMENT",
  "TEST",
  "REVIEW",
  "REPAIR",
  "DOCS",
  "DELIVER",
];
export function App() {
  const runId = location.pathname.match(/^\/runs\/([^/]+)$/)?.[1] ?? null;
  const { snapshot, events, connection, error } = useRun(runId);
  const [projects, setProjects] = useState<Project[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [historyPage, setHistoryPage] = useState(0);
  const [homeError, setHomeError] = useState<string | null>(null);
  useEffect(() => {
    const abort = new AbortController();
    Promise.all([
      get<Project[]>("/api/projects", abort.signal),
      get<Run[]>("/api/runs", abort.signal),
    ])
      .then(([projectList, runList]) => {
        setProjects(projectList);
        setRuns(runList);
      })
      .catch((failure: unknown) => {
        if (!abort.signal.aborted) setHomeError(String(failure));
      });
    return () => abort.abort();
  }, []);
  const project = projects.find((item) => item.id === snapshot?.run.project_id);
  const workers =
    snapshot?.actors.filter((actor) => actor.session.actor_type === "AGENT") ??
    [];
  const criteria = snapshot?.goal?.criteria ?? [];
  const passed = criteria.filter((item) => item.status === "PASS").length;
  const failed = criteria.filter((item) => item.status === "FAIL").length;

  return (
    <div className="shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="Orqalis home">
          <span className="brand-mark">◈</span>ORQALIS
          <span className="local-tag">LOCAL</span>
        </a>
        <div className="workspace">
          <span className="workspace-icon">⌘</span>
          <div>
            <strong>{project?.name ?? "Your workspace"}</strong>
            <small>
              {projects.length} registered{" "}
              {projects.length === 1 ? "project" : "projects"}
            </small>
          </div>
        </div>
        <span className="nav-caption">WORKSPACE</span>
        <nav aria-label="Primary">
          <a href="/" className={!runId ? "selected" : ""}>
            <span aria-hidden="true">▦</span>Overview
          </a>
          <a
            href={runId ? `/runs/${runId}` : "/"}
            className={runId ? "selected" : ""}
          >
            <span aria-hidden="true">◎</span>Mission Control
          </a>
        </nav>
        <div className="nav-caption recent-heading">
          RECENT RUNS <span>{runs.length}</span>
        </div>
        <nav className="recent-runs" aria-label="Recent runs">
          {runs.slice(0, 7).map((run) => (
            <a
              key={run.id}
              href={`/runs/${run.id}`}
              className={run.id === runId ? "current-run" : ""}
            >
              <i
                className={`run-dot dot-${run.state.toLowerCase()} tone-${statusTone(run.state)}`}
              />
              <span>{run.request}</span>
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="connection-dot" />
          Orqalis Core<small>Local execution · durable state</small>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            Workspace <span>/</span>{" "}
            <strong>{runId ? "Mission Control" : "Overview"}</strong>
          </div>
          <ThemeControl />
          <span className="connection" role="status">
            <i className={connection === "Live" ? "green" : "amber"} />
            {runId ? connection : "Local instance"}
          </span>
        </header>
        <main id="main-content">
          {(error || homeError) && (
            <div className="error-banner" role="alert">
              {error ?? homeError}.{" "}
              <button onClick={() => location.reload()}>
                Retry connection
              </button>
            </div>
          )}
          {!runId ? (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">YOUR ENGINEERING WORKSPACE</span>
                  <h1>Local Mission Control</h1>
                  <p>Runs, agents, and evidence. One view of your work.</p>
                </div>
              </div>
              <section className="panel home-runs">
                <div className="section-heading">
                  <h2>Run history</h2>
                  <span>{runs.length} runs</span>
                </div>
                {runs.length ? (
                  runs
                    .slice(historyPage * 50, (historyPage + 1) * 50)
                    .map((run) => (
                      <a
                        className="history-row"
                        key={run.id}
                        href={`/runs/${run.id}`}
                      >
                        <div>
                          <strong>{run.request}</strong>
                          <small>
                            {run.target_branch} ·{" "}
                            {new Date(run.created_at).toLocaleString()}
                          </small>
                        </div>
                        <Badge status={run.state} />
                        <span>↗</span>
                      </a>
                    ))
                ) : (
                  <div className="empty">
                    <span>◎</span>
                    <h3>No runs yet</h3>
                    <p>Runs created through Orqalis will appear here.</p>
                  </div>
                )}
                {runs.length > 50 && (
                  <nav
                    className="section-heading"
                    aria-label="Run history pages"
                  >
                    <button
                      disabled={historyPage === 0}
                      onClick={() => setHistoryPage((p) => p - 1)}
                    >
                      Previous runs
                    </button>
                    <span>
                      Page {historyPage + 1} of {Math.ceil(runs.length / 50)}
                    </span>
                    <button
                      disabled={(historyPage + 1) * 50 >= runs.length}
                      onClick={() => setHistoryPage((p) => p + 1)}
                    >
                      Next runs
                    </button>
                  </nav>
                )}
              </section>
            </>
          ) : !snapshot ? (
            <div className="empty">
              <span>◎</span>
              <h2>{error ? "Run unavailable" : "Loading run"}</h2>
              <p>Reading persisted execution state…</p>
            </div>
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">
                    {project?.name ?? "PROJECT"}{" "}
                    <span className="separator">/</span> RUN{" "}
                    {snapshot.run.id.slice(0, 8)}
                  </span>
                  <h1>{snapshot.goal?.goal.goal ?? snapshot.run.request}</h1>
                  <div className="run-meta">
                    <span>⑂ {snapshot.run.target_branch}</span>
                    <span>◷ {snapshot.run.base_commit.slice(0, 8)}</span>
                    <span>Goal v{snapshot.goal?.goal.version ?? "—"}</span>
                  </div>
                </div>
                <Badge status={snapshot.run.state} />
              </div>
              <section className="run-summary" aria-label="Run summary">
                <div className="summary-progress">
                  <span className="eyebrow">Plan completion</span>
                  <strong>{Math.round(snapshot.plan_completion)}%</strong>
                  <div
                    role="progressbar"
                    aria-label="Plan completion"
                    aria-valuenow={snapshot.plan_completion}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    className="progress-track"
                  >
                    <i style={{ width: snapshot.plan_completion + "%" }} />
                  </div>
                  <small>
                    {snapshot.task_counts.SUCCEEDED}/
                    {visibleTasks(snapshot).length} succeeded
                  </small>
                </div>
                <dl>
                  <div>
                    <dt>Run elapsed</dt>
                    <dd className="numeric">
                      {duration(snapshot.timing.wall_ms)}
                    </dd>
                  </div>
                  <div>
                    <dt>Agents working</dt>
                    <dd>
                      {
                        workers.filter((a) => a.session.status === "WORKING")
                          .length
                      }{" "}
                      / {workers.length}
                    </dd>
                  </div>
                  <div>
                    <dt>Remaining</dt>
                    <dd>
                      {
                        visibleTasks(snapshot).filter(
                          (t) =>
                            !["SUCCEEDED", "CANCELLED", "SKIPPED"].includes(
                              t.status,
                            ),
                        ).length
                      }
                    </dd>
                  </div>
                  <div>
                    <dt>Blocked / failed</dt>
                    <dd>
                      {snapshot.task_counts.BLOCKED} /{" "}
                      {snapshot.task_counts.FAILED}
                    </dd>
                  </div>
                  <div>
                    <dt>Task retries</dt>
                    <dd>{retryCount(snapshot)}</dd>
                  </div>
                  <div>
                    <dt>Acceptance</dt>
                    <dd>
                      {passed}/{criteria.length} pass
                      {failed ? " · " + failed + " fail" : ""}
                    </dd>
                  </div>
                  <div>
                    <dt>Changed files</dt>
                    <dd>
                      {snapshot.guardians.at(-1)?.changes.length ??
                        "Not inspected"}
                    </dd>
                  </div>
                  <div>
                    <dt>Test tool calls</dt>
                    <dd>
                      {
                        snapshot.tools.filter((t) => t.tool === "test.run")
                          .length
                      }
                    </dd>
                  </div>
                </dl>
              </section>
              <section className="phase-strip" aria-label="Workflow phases">
                {phases.map((phase, index) => {
                  const complete = snapshot.phases.some(
                    (item) =>
                      item.execution.phase === phase &&
                      item.execution.status === "SUCCEEDED",
                  );
                  return (
                    <div
                      key={phase}
                      className={
                        snapshot.run.ui_phase === phase
                          ? "active-phase"
                          : complete
                            ? "done-phase"
                            : ""
                      }
                    >
                      <span>
                        {complete ? "✓" : String(index + 1).padStart(2, "0")}
                      </span>
                      <strong>{label(phase)}</strong>
                      {snapshot.run.ui_phase === phase && <i />}
                    </div>
                  );
                })}
              </section>
              <RunControls snapshot={snapshot} />
              <WorkspaceViews snapshot={snapshot} runs={runs} events={events} />
              <footer className="run-footer">
                <span>
                  Snapshot {new Date(snapshot.server_time).toLocaleTimeString()}{" "}
                  · sequence {snapshot.last_event_sequence}
                </span>
                <span>
                  Progress reflects the current plan. Timings come from Orqalis
                  Core.
                </span>
              </footer>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
