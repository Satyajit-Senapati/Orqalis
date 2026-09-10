import { useState } from "react";
import { BrainView } from "./BrainView";
import { DeliveryView } from "./DeliveryView";
import { EvidenceView } from "./EvidenceView";
import { ExecutionGraph } from "./Graphs";
import { MetricsView } from "./MetricsView";
import { Timeline } from "./Timeline";
import { Inspector } from "./Inspector";
import {
  ActivityView,
  AgentList,
  SkillsView,
  TaskList,
} from "./OperationalViews";
import { nextWork, type Selection } from "./runtime";
import { Badge } from "./ui";
import type { Event, Run, Snapshot } from "./types";

const views = [
  "Mission",
  "Graph",
  "Timeline",
  "Acceptance",
  "Project Brain",
  "Delivery",
  "Metrics",
  "Tasks",
  "Agents",
  "Skills",
  "Activity",
] as const;
type View = (typeof views)[number];
export function WorkspaceViews({
  snapshot: s,
  runs,
  events,
}: {
  snapshot: Snapshot;
  runs: Run[];
  events: Event[];
}) {
  const [view, setView] = useState<View>("Mission");
  const [selection, inspect] = useState<Selection>(null);
  const [file, setFile] = useState("");
  const [developer, setDeveloper] = useState(false);
  function openFile(path: string) {
    setFile(path);
    setView("Delivery");
    inspect(null);
  }
  function openMemory() {
    setView("Project Brain");
    inspect(null);
  }
  return (
    <>
      {s.blockers.length > 0 && (
        <section className="blockers-panel" aria-label="Current blockers">
          <h2>Needs attention</h2>
          <ul>
            {s.blockers.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
          <p>
            {s.run.state === "HUMAN_REVIEW_REQUIRED"
              ? "The repair limit was reached. Human review is required."
              : "Resolve the recorded blocker before execution can continue."}
          </p>
        </section>
      )}
      <div className="workspace-tabs" role="tablist" aria-label="Run views">
        {views.map((name, index) => (
          <button
            key={name}
            tabIndex={view === name ? 0 : -1}
            role="tab"
            id={"tab-" + index}
            aria-selected={view === name}
            aria-controls="workspace-panel"
            onClick={() => setView(name)}
            onKeyDown={(e) => {
              if (["ArrowRight", "ArrowLeft", "Home", "End"].includes(e.key)) {
                e.preventDefault();
                const next =
                  e.key === "Home"
                    ? 0
                    : e.key === "End"
                      ? views.length - 1
                      : (index +
                          (e.key === "ArrowRight" ? 1 : views.length - 1)) %
                        views.length;
                setView(views[next]);
                document.getElementById("tab-" + next)?.focus();
              }
            }}
          >
            {name}
          </button>
        ))}
      </div>
      <div
        id="workspace-panel"
        role="tabpanel"
        aria-labelledby={"tab-" + views.indexOf(view)}
      >
        {view === "Mission" && (
          <div className="mission-stack">
            <div className="mission-next">
              <span className="eyebrow">Execution checkpoint</span>
              <p>{nextWork(s)}</p>
            </div>
            <div className="mission-center">
              <ExecutionGraph
                snapshot={s}
                inspect={inspect}
                initialMode="orchestration"
              />
              <AgentList snapshot={s} inspect={inspect} compact />
            </div>
            <div className="mission-bottom">
              <section className="panel acceptance-panel">
                <div className="section-heading">
                  <h2>Acceptance contract</h2>
                  <button
                    className="text-link"
                    onClick={() => setView("Acceptance")}
                  >
                    View evidence ↗
                  </button>
                </div>
                {s.goal?.criteria.length ? (
                  s.goal.criteria.map((c) => (
                    <div className="criterion" key={c.id}>
                      <div>
                        <span className="criterion-key">{c.key}</span>
                        <Badge status={c.status} />
                      </div>
                      <p>{c.description}</p>
                      <small>
                        {c.evidence_refs.length} evidence{" "}
                        {c.evidence_refs.length === 1 ? "record" : "records"} ·{" "}
                        {c.validation_spec.kind}
                      </small>
                    </div>
                  ))
                ) : (
                  <p className="panel-body">
                    No acceptance contract has been defined yet.
                  </p>
                )}
              </section>
              <ActivityView
                snapshot={s}
                events={events}
                inspect={inspect}
                compact
              />
            </div>
          </div>
        )}
        {view === "Graph" && <ExecutionGraph snapshot={s} inspect={inspect} />}
        {view === "Tasks" && <TaskList snapshot={s} inspect={inspect} />}
        {view === "Agents" && <AgentList snapshot={s} inspect={inspect} />}
        {view === "Skills" && <SkillsView snapshot={s} inspect={inspect} />}
        {view === "Activity" && (
          <ActivityView snapshot={s} events={events} inspect={inspect} />
        )}
        {view === "Timeline" && <Timeline snapshot={s} />}
        {view === "Acceptance" && <EvidenceView snapshot={s} />}
        {view === "Project Brain" && <BrainView snapshot={s} />}
        {view === "Delivery" && (
          <DeliveryView snapshot={s} initialPath={file} inspect={inspect} />
        )}
        {view === "Metrics" && <MetricsView snapshot={s} runs={runs} />}
      </div>
      <label className="developer-toggle">
        <input
          type="checkbox"
          checked={developer}
          onChange={(e) => setDeveloper(e.target.checked)}
        />{" "}
        Developer mode: structured snapshot
      </label>
      {developer && (
        <pre className="developer-json">{JSON.stringify(s, null, 2)}</pre>
      )}
      <Inspector
        selection={selection}
        snapshot={s}
        events={events}
        inspect={inspect}
        openFile={openFile}
        openMemory={openMemory}
      />
    </>
  );
}
