import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { duration } from "./api";
import fixture from "./fixtures/runtime-trace.json";
import { Timeline } from "./Timeline";
import { TraceView } from "./TraceView";
import type { Snapshot } from "./types";

const snapshot = fixture as unknown as Snapshot;

describe("trace and critical path from an executed parallel repair fixture", () => {
  it("renders all operation categories, parents and explicit missing durations", () => {
    const html = renderToStaticMarkup(<TraceView snapshot={snapshot} />);
    for (const kind of ["run", "phase", "task", "actor", "model", "tool"]) {
      expect(html).toContain(kind + ": ");
    }
    for (const node of snapshot.trace!) expect(html).toContain(node.entity_id.slice(0, 8));
    expect(html).toContain("Not reported");
    expect(html).not.toContain("private-provider-output-sentinel");
  });
  it("uses the backend measured path and highlights its existing intervals", () => {
    const html = renderToStaticMarkup(<Timeline snapshot={snapshot} />);
    expect(html).toContain("Measured critical path");
    expect(html).toContain(duration(snapshot.statistics.critical_path_working_ms));
    expect(html).toContain("critical-path-bar");
    for (const id of snapshot.statistics.critical_path_task_ids) {
      expect(html).toContain(snapshot.tasks.find((task) => task.id === id)!.description);
    }
    expect(snapshot.statistics.max_parallel_tasks).toBe(2);
    expect(snapshot.plan!.version).toBeGreaterThan(1);
  });
  it("supports older snapshots with no trace and empty task paths", () => {
    const older = { ...snapshot, trace: undefined, timeline: [], statistics: { ...snapshot.statistics, critical_path_task_ids: [] } };
    const html = renderToStaticMarkup(<Timeline snapshot={older} />);
    expect(html).toContain("No correlated operations recorded");
    expect(html).toContain("No task path measured yet");
    expect(html).toContain("No persisted execution intervals yet");
  });
});
