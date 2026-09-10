import { useState, type ReactNode } from "react";
import { BrainView } from "./BrainView";
import { DeliveryView } from "./DeliveryView";
import { EvidenceView } from "./EvidenceView";
import { ExecutionGraph } from "./Graphs";
import { MetricsView } from "./MetricsView";
import { Timeline } from "./Timeline";
import type { Run, Snapshot } from "./types";

const views = ["Mission", "Graph", "Timeline", "Acceptance", "Project Brain", "Delivery", "Metrics"] as const;
export function WorkspaceViews({ snapshot, runs, children }: { snapshot: Snapshot; runs: Run[]; children: ReactNode }) {
  const [view, setView] = useState<typeof views[number]>("Mission");
  const [developer, setDeveloper] = useState(false);
  return <>
    {snapshot.blockers.length > 0 && <section className="blockers-panel" aria-label="Current blockers"><h2>Needs attention</h2><ul>{snapshot.blockers.map(text => <li key={text}>{text}</li>)}</ul>
      <p>{snapshot.run.state === "HUMAN_REVIEW_REQUIRED" ? "The repair limit was reached. Human review is required." : "Resolve the recorded blocker before execution can continue."}</p></section>}
    <div className="workspace-tabs" role="tablist" aria-label="Run views">{views.map((name, index) => <button key={name}
      tabIndex={view === name ? 0 : -1} role="tab" id={`tab-${index}`} aria-selected={view === name} aria-controls="workspace-panel"
      onClick={() => setView(name)} onKeyDown={e => {
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
          e.preventDefault(); const next = (index + (e.key === "ArrowRight" ? 1 : views.length - 1)) % views.length;
          setView(views[next]); document.getElementById(`tab-${next}`)?.focus();
        }
      }}>{name}</button>)}</div>
    <div id="workspace-panel" role="tabpanel" aria-labelledby={`tab-${views.indexOf(view)}`}>
      {view === "Mission" && children}
      {view === "Graph" && <ExecutionGraph snapshot={snapshot} />}
      {view === "Timeline" && <Timeline snapshot={snapshot} />}
      {view === "Acceptance" && <EvidenceView snapshot={snapshot} />}
      {view === "Project Brain" && <BrainView snapshot={snapshot} />}
      {view === "Delivery" && <DeliveryView snapshot={snapshot} />}
      {view === "Metrics" && <MetricsView snapshot={snapshot} runs={runs} />}
    </div>
    <label className="developer-toggle"><input type="checkbox" checked={developer} onChange={e => setDeveloper(e.target.checked)} /> Developer mode: structured snapshot</label>
    {developer && <pre className="developer-json">{JSON.stringify(snapshot, null, 2)}</pre>}
  </>;
}
