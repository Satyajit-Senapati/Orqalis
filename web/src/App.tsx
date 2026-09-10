import { useEffect, useState } from "react";
import { WorkspaceViews } from "./WorkspaceViews";
import { ThemeControl, RunControls } from "./Controls";
import { duration, get, useRun } from "./api";
import type { Actor, Project, Run, Snapshot } from "./types";

const phases = ["CONTEXT", "GOAL", "PLAN", "IMPLEMENT", "TEST", "REVIEW", "REPAIR", "DOCS", "DELIVER"];
const label = (value: string) => value.replaceAll("_", " ").toLowerCase();
function Badge({ status }: { status: string }) {
  return <span className={`badge status-${status.toLowerCase()}`}><i />{label(status)}</span>;
}
function ActorCard({ actor, snapshot }: { actor: Actor; snapshot: Snapshot }) {
  const { session, timing } = actor;
  const coordinator = session.actor_type === "ORCHESTRATOR";
  const task = snapshot.tasks.find((item) => item.id === session.current_task_id);
  return <article className={`actor-card ${coordinator ? "coordinator" : ""}`}>
    <div className="actor-heading">
      <div className={`actor-icon ${coordinator ? "main-icon" : ""}`}>{coordinator ? "◎" : "◇"}</div>
      <div><h3>{coordinator ? "Orchestrator" : label(session.role ?? "agent")}</h3>
        <p>{coordinator ? "Workflow controller" : session.provider ? `${session.provider} · ${session.model ?? "model not reported"}` : "Provider not assigned"}</p></div>
      <Badge status={session.status} />
    </div>
    <div className="assignment"><span className="eyebrow">{coordinator ? "Current phase" : "Current assignment"}</span>
      <strong>{coordinator ? label(snapshot.run.ui_phase) : task?.description ?? "No active assignment"}</strong></div>
    <div className="actor-timer"><span>Session elapsed</span><b>{duration(timing.wall_ms)}</b></div>
    <div className="time-breakdown">
      <div><i className="green" />Working <strong>{duration(timing.active_ms)}</strong></div>
      <div><i className="amber" />Waiting <strong>{duration(timing.waiting_ms)}</strong></div>
      <div><i className="rose" />Blocked <strong>{duration(timing.blocked_ms)}</strong></div>
    </div>
    {!coordinator && <div className="skills"><span>Skills</span>{session.loaded_skills.length ? session.loaded_skills.map((skill) => <small key={skill}>{skill}</small>) : <small>No skills loaded</small>}</div>}
    {coordinator && <div className="coordinator-footer"><span>Plan v{snapshot.run.plan_version}</span><span>{snapshot.task_counts.READY} ready · {snapshot.task_counts.RUNNING} running</span></div>}
  </article>;
}

export function App() {
  const runId = location.pathname.match(/^\/runs\/([^/]+)$/)?.[1] ?? null;
  const { snapshot, events, connection, error } = useRun(runId);
  const [projects, setProjects] = useState<Project[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [homeError, setHomeError] = useState<string | null>(null);
  useEffect(() => {
    const abort = new AbortController();
    Promise.all([get<Project[]>("/api/projects", abort.signal), get<Run[]>("/api/runs", abort.signal)])
      .then(([projectList, runList]) => { setProjects(projectList); setRuns(runList); })
      .catch((failure: unknown) => { if (!abort.signal.aborted) setHomeError(String(failure)); });
    return () => abort.abort();
  }, []);
  const project = projects.find((item) => item.id === snapshot?.run.project_id);
  const coordinator = snapshot?.actors.find((actor) => actor.session.actor_type === "ORCHESTRATOR");
  const workers = snapshot?.actors.filter((actor) => actor.session.actor_type === "AGENT") ?? [];
  const criteria = snapshot?.goal?.criteria ?? [];
  const passed = criteria.filter((item) => item.status === "PASS").length;
  const failed = criteria.filter((item) => item.status === "FAIL").length;

  return <div className="shell">
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="Orqalis home"><span className="brand-mark">◈</span>ORQALIS<span className="local-tag">LOCAL</span></a>
      <div className="workspace"><span className="workspace-icon">⌘</span><div><strong>{project?.name ?? "Your workspace"}</strong><small>{projects.length} registered {projects.length === 1 ? "project" : "projects"}</small></div></div>
      <span className="nav-caption">WORKSPACE</span>
      <nav aria-label="Primary"><a href="/" className={!runId ? "selected" : ""}><span>▦</span>Overview</a><a href={runId ? `/runs/${runId}` : "/"} className={runId ? "selected" : ""}><span>◎</span>Mission Control</a></nav>
      <div className="nav-caption recent-heading">RECENT RUNS <span>{runs.length}</span></div>
      <nav className="recent-runs" aria-label="Recent runs">{runs.slice(0, 7).map((run) => <a key={run.id} href={`/runs/${run.id}`} className={run.id === runId ? "current-run" : ""}><i className={`run-dot dot-${run.state.toLowerCase()}`} /><span>{run.request}</span></a>)}</nav>
      <div className="sidebar-bottom"><span className="connection-dot" />Orqalis Core<small>Local execution · durable state</small></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div>Workspace <span>/</span> <strong>{runId ? "Mission Control" : "Overview"}</strong></div><ThemeControl /><span className="connection" role="status"><i className={connection === "Live" ? "green" : "amber"} />{runId ? connection : "Local instance"}</span></header>
      <main>
        {(error || homeError) && <div className="error-banner" role="alert">{error ?? homeError}. Reconnecting to Orqalis Core.</div>}
        {!runId ? <><div className="page-heading"><div><span className="eyebrow">YOUR ENGINEERING WORKSPACE</span><h1>Local Mission Control</h1><p>Runs, agents, and evidence. One view of your work.</p></div></div>
          <section className="panel home-runs"><div className="section-heading"><h2>Run history</h2><span>{runs.length} runs</span></div>{runs.length ? runs.map((run) => <a className="history-row" key={run.id} href={`/runs/${run.id}`}><div><strong>{run.request}</strong><small>{run.target_branch} · {new Date(run.created_at).toLocaleString()}</small></div><Badge status={run.state} /><span>↗</span></a>) : <div className="empty"><span>◎</span><h3>No runs yet</h3><p>Runs created through Orqalis will appear here.</p></div>}</section></> :
          !snapshot ? <div className="empty"><span>◎</span><h2>Loading run</h2><p>Reading persisted execution state…</p></div> : <>
            <div className="page-heading"><div><span className="eyebrow">{project?.name ?? "PROJECT"} <span className="separator">/</span> RUN {snapshot.run.id.slice(0, 8)}</span><h1>{snapshot.goal?.goal.goal ?? snapshot.run.request}</h1><div className="run-meta"><span>⑂ {snapshot.run.target_branch}</span><span>◷ {snapshot.run.base_commit.slice(0, 8)}</span><span>Goal v{snapshot.goal?.goal.version ?? "—"}</span></div></div><Badge status={snapshot.run.state} /></div>
            <div className="metrics-grid">
              <section className="metric progress-metric"><span>PLAN COMPLETION</span><strong>{Math.round(snapshot.plan_completion)}<small>%</small></strong><div role="progressbar" aria-label="Plan completion" aria-valuenow={snapshot.plan_completion} aria-valuemin={0} aria-valuemax={100} className="progress-track"><i style={{ width: `${snapshot.plan_completion}%` }} /></div><p>{snapshot.task_counts.SUCCEEDED} of {snapshot.plan?.tasks.length ?? 0} tasks succeeded</p></section>
              <section className="metric"><span>RUN ELAPSED</span><strong className="numeric">{duration(snapshot.timing.wall_ms)}</strong><p>From persisted execution timestamps</p></section>
              <section className="metric"><span>ACTORS WORKING</span><strong>{snapshot.actors.filter((actor) => actor.session.status === "WORKING").length}<small> / {snapshot.actors.length}</small></strong><p>{workers.length} agents + Orchestrator</p></section>
              <section className="metric"><span>ACCEPTANCE</span><strong>{passed}<small> / {criteria.length}</small></strong><p>{failed ? `${failed} failed · needs attention` : `${criteria.length - passed} awaiting validation`}</p></section>
            </div>
            <section className="phase-strip" aria-label="Workflow phases">{phases.map((phase, index) => {
              const complete = snapshot.phases.some((item) => item.execution.phase === phase && item.execution.status === "SUCCEEDED");
              return <div key={phase} className={snapshot.run.ui_phase === phase ? "active-phase" : complete ? "done-phase" : ""}><span>{complete ? "✓" : String(index + 1).padStart(2, "0")}</span><strong>{label(phase)}</strong>{snapshot.run.ui_phase === phase && <i />}</div>;
            })}</section>
            <RunControls snapshot={snapshot} />
            <WorkspaceViews snapshot={snapshot} runs={runs}>
            <div className="section-heading runtime-heading"><div><h2>Runtime</h2><span>Who is working, and on what</span></div><span className="subtle">Authoritative server state</span></div>
            <div className="runtime-layout"><div className="actors-column">{coordinator && <ActorCard actor={coordinator} snapshot={snapshot} />}<div className="workers-grid">{workers.map((actor) => <ActorCard key={actor.session.id} actor={actor} snapshot={snapshot} />)}</div>{workers.length === 0 && <div className="agent-empty"><span>◇</span><div><strong>No agent sessions yet</strong><p>Agents appear when Orqalis assigns work.</p></div></div>}</div>
              <aside className="run-details"><section className="panel acceptance-panel"><div className="section-heading"><h2>Acceptance contract</h2><span>{passed}/{criteria.length}</span></div>{criteria.map((criterion) => <div className="criterion" key={criterion.id}><div><span className="criterion-key">{criterion.key}</span><Badge status={criterion.status} /></div><p>{criterion.description}</p><small>{label(criterion.validation_spec.kind)} · {criterion.evidence_refs.length} evidence {criterion.evidence_refs.length === 1 ? "record" : "records"}</small></div>)}</section><section className="panel repair-panel"><div><span className="eyebrow">REPAIR LOOP</span><strong>{snapshot.run.repair_iteration}<small> / {snapshot.run.max_repair_iterations}</small></strong></div><p>{snapshot.run.repair_iteration ? "Targeted repair in the current run" : "No repair iterations recorded"}</p></section></aside></div>
            <section className="panel task-panel"><div className="section-heading"><h2>Task plan</h2><span>{snapshot.plan?.tasks.length ?? 0} tasks · version {snapshot.run.plan_version}</span></div>{snapshot.plan ? <div className="table-scroll"><table><caption className="sr-only">Current dependency-aware task plan</caption><thead><tr><th>Task</th><th>Agent role</th><th>Status</th><th>Dependencies</th><th>Attempt</th><th>Elapsed</th></tr></thead><tbody>{snapshot.plan.tasks.map((task) => <tr key={task.id}><td><strong>{task.description}</strong><small>{task.id.slice(0, 8)}</small></td><td>{label(task.preferred_role)}</td><td><Badge status={task.status} /></td><td>{snapshot.plan?.dependencies.filter((edge) => edge.task_id === task.id).map((edge) => snapshot.tasks.find((item) => item.id === edge.depends_on_task_id)?.description).join(", ") || "—"}</td><td>{task.attempt_count}</td><td className="numeric">{duration(snapshot.task_timing[task.id]?.wall_ms ?? 0)}</td></tr>)}</tbody></table></div> : <div className="empty small-empty"><p>No plan has been installed for this goal.</p></div>}</section>
            </WorkspaceViews>
            <section className="panel activity-panel"><div className="section-heading"><h2>Structured activity</h2><span>Event cursor #{snapshot.last_event_sequence}</span></div>{events.slice(-12).reverse().map((event) => <div className="activity-row" key={event.id}><time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleTimeString()}</time><i /><div><strong>{label(event.event_type)}</strong>{event.payload.summary && <span>{event.payload.summary}</span>}</div><small>#{event.sequence}</small></div>)}</section>
            <footer className="run-footer"><span>Snapshot {new Date(snapshot.server_time).toLocaleTimeString()} · sequence {snapshot.last_event_sequence}</span><span>Progress reflects the current plan. Timings come from Orqalis Core.</span></footer>
          </>}
      </main>
    </div>
  </div>;
}
