import { useEffect, useRef, useState } from "react";
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
  const [mountedViews, setMountedViews] = useState<Set<View>>(
    () => new Set(["Mission"]),
  );
  const [selection, inspect] = useState<Selection>(null);
  const [fileRequest, setFileRequest] = useState({
    path: "",
    sequence: 0,
  });
  const [developer, setDeveloper] = useState(false);
  const [focusRequest, setFocusRequest] = useState(0);
  const pendingTabFocus = useRef<View | null>(null);
  const tabs = useRef<Array<HTMLButtonElement | null>>([]);
  function activateView(next: View, moveFocus = false) {
    setMountedViews((current) => {
      if (current.has(next)) return current;
      const updated = new Set(current);
      updated.add(next);
      return updated;
    });
    if (moveFocus) {
      pendingTabFocus.current = next;
      setFocusRequest((current) => current + 1);
    }
    setView(next);
  }
  useEffect(() => {
    const target = pendingTabFocus.current;
    if (!target || target !== view) return;
    const frame = requestAnimationFrame(() => {
      tabs.current[views.indexOf(target)]?.focus();
      if (pendingTabFocus.current === target) pendingTabFocus.current = null;
    });
    return () => cancelAnimationFrame(frame);
  }, [focusRequest, view]);
  function openFile(path: string) {
    setFileRequest((current) => ({
      path,
      sequence: current.sequence + 1,
    }));
    activateView("Delivery", true);
    inspect(null);
  }
  function openMemory() {
    activateView("Project Brain", true);
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
            ref={(node) => {
              tabs.current[index] = node;
            }}
            tabIndex={view === name ? 0 : -1}
            role="tab"
            id={"tab-" + index}
            aria-selected={view === name}
            aria-controls={"workspace-panel-" + index}
            onClick={() => activateView(name)}
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
                activateView(views[next]);
                tabs.current[next]?.focus();
              }
            }}
          >
            {name}
          </button>
        ))}
      </div>
      {views.map((panelView, index) => (
        <div
          key={panelView}
          id={"workspace-panel-" + index}
          role="tabpanel"
          aria-labelledby={"tab-" + index}
          hidden={view !== panelView}
        >
          {mountedViews.has(panelView) && (
            <>
              {panelView === "Mission" && (
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
                      active={view === "Mission"}
                    />
                    <AgentList snapshot={s} inspect={inspect} compact />
                  </div>
                  <div className="mission-bottom">
                    <section className="panel acceptance-panel">
                      <div className="section-heading">
                        <h2>Acceptance contract</h2>
                        <button
                          className="text-link"
                          onClick={() => activateView("Acceptance", true)}
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
                              {c.evidence_refs.length === 1
                                ? "record"
                                : "records"}{" "}
                              · {c.validation_spec.kind}
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
              {panelView === "Graph" && (
                <ExecutionGraph
                  snapshot={s}
                  inspect={inspect}
                  active={view === "Graph"}
                />
              )}
              {panelView === "Tasks" && (
                <TaskList snapshot={s} inspect={inspect} />
              )}
              {panelView === "Agents" && (
                <AgentList snapshot={s} inspect={inspect} />
              )}
              {panelView === "Skills" && (
                <SkillsView snapshot={s} inspect={inspect} />
              )}
              {panelView === "Activity" && (
                <ActivityView snapshot={s} events={events} inspect={inspect} />
              )}
              {panelView === "Timeline" && <Timeline snapshot={s} />}
              {panelView === "Acceptance" && <EvidenceView snapshot={s} />}
              {panelView === "Project Brain" && <BrainView snapshot={s} />}
              {panelView === "Delivery" && (
                <DeliveryView
                  snapshot={s}
                  initialPath={fileRequest.path}
                  initialPathRequest={fileRequest.sequence}
                  inspect={inspect}
                />
              )}
              {panelView === "Metrics" && (
                <MetricsView snapshot={s} runs={runs} />
              )}
            </>
          )}
        </div>
      ))}
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
