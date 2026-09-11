import { useEffect, useState } from "react";
import { WorkspaceViews } from "./WorkspaceViews";
import { Overview } from "./Overview";
import { Sidebar } from "./Sidebar";
import { RunControls } from "./Controls";
import { duration, get, useRun } from "./api";
import type { Project, Run } from "./types";

import { Badge, label } from "./ui";
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
  const requestedProjectId = !runId
    ? new URLSearchParams(location.search).get("project")
    : null;
  const { snapshot, events, connection, error } = useRun(runId);
  const [projects, setProjects] = useState<Project[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [homeError, setHomeError] = useState<string | null>(null);
  const [homeLoading, setHomeLoading] = useState(true);
  useEffect(() => {
    const abort = new AbortController();
    void Promise.allSettled([
      get<Project[]>("/api/projects", abort.signal),
      get<Run[]>("/api/runs", abort.signal),
    ]).then(([projectResult, runResult]) => {
      if (abort.signal.aborted) return;
      const failures: string[] = [];
      if (projectResult.status === "fulfilled") {
        setProjects(projectResult.value);
      } else {
        failures.push("Projects: " + String(projectResult.reason));
      }
      if (runResult.status === "fulfilled") {
        setRuns(runResult.value);
      } else {
        failures.push("Runs: " + String(runResult.reason));
      }
      setHomeError(failures.length ? failures.join(". ") : null);
      setHomeLoading(false);
    });
    return () => abort.abort();
  }, []);
  const selectedProjectId =
    snapshot?.run.project_id ??
    (projects.some((item) => item.id === requestedProjectId)
      ? requestedProjectId
      : null);
  const project = projects.find((item) => item.id === selectedProjectId);
  const displayedRuns = snapshot
    ? [snapshot.run, ...runs.filter((run) => run.id !== snapshot.run.id)]
    : runs;
  const coreStatus = runId
    ? connection
    : homeLoading
      ? "Connecting"
      : homeError
        ? "Degraded"
        : "Ready";
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
      <Sidebar
        projects={projects}
        runs={displayedRuns}
        runId={runId}
        selectedProjectId={selectedProjectId}
        coreStatus={coreStatus}
      />
      <div className="main-shell">
        <header className="topbar">
          <div>
            <a className="breadcrumb-link" href="/">
              Workspace
            </a>{" "}
            <span>/</span>{" "}
            <strong>
              {runId ? "Mission Control" : (project?.name ?? "Overview")}
            </strong>
          </div>
          <span className="connection" role="status">
            <i
              className={
                ["Live", "Ready"].includes(coreStatus) ? "green" : "amber"
              }
            />
            {runId ? connection : coreStatus}
          </span>
        </header>
        <main id="main-content" tabIndex={-1}>
          {(error || homeError) && (
            <div className="error-banner" role="alert">
              {error ?? homeError}.{" "}
              <button onClick={() => location.reload()}>
                Retry connection
              </button>
            </div>
          )}
          {!runId ? (
            homeLoading ? (
              <div className="empty">
                <span>◇</span>
                <h2>Loading workspace</h2>
                <p>Reading registered projects and persisted runs…</p>
              </div>
            ) : (
              <Overview
                projects={projects}
                runs={runs}
                selectedProjectId={selectedProjectId}
              />
            )
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
              <WorkspaceViews
                snapshot={snapshot}
                runs={displayedRuns}
                events={events}
              />
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
