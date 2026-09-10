import { describe, expect, it } from "vitest";
import { filterEvents } from "./OperationalViews";
import { nextWork, retryCount, taskRelations, taskFiles } from "./runtime";
import type { Event, Snapshot, Task } from "./types";

const task = (id: string, status: Task["status"] = "PENDING") => ({
  id,
  status,
  description: id,
  preferred_role: "developer",
  expected_outcome: "Observed result",
  attempt_count: 1,
  acceptance_criterion_ids: [],
  required_capabilities: [],
  expected_artifacts: [],
  parent_task_id: null,
  created_at: "2026-09-10T12:00:00Z",
  ready_at: null,
  started_at: null,
  completed_at: null,
});
const a = task("source", "SUCCEEDED"),
  b = task("test", "READY");
const snapshot = {
  run: { state: "EXECUTING" },
  tasks: [a, b],
  preparation_tasks: [],
  plan: {
    tasks: [a, b],
    dependencies: [{ task_id: b.id, depends_on_task_id: a.id }],
  },
  artifacts: [{ task_id: a.id, path_or_uri: "main.py" }],
  evidence: [],
} as unknown as Snapshot;

describe("runtime presentation preserves recorded relationships", () => {
  it("reports ready work without predicting future workflow", () => {
    expect(nextWork(snapshot)).toContain("Ready for dispatch: test");
    expect(
      nextWork({ ...snapshot, run: { ...snapshot.run, state: "BLOCKED" } }),
    ).toContain("suspended");
    expect(
      nextWork({ ...snapshot, run: { ...snapshot.run, state: "COMPLETED" } }),
    ).toContain("Delivered");
  });
  it("links prerequisites, dependents and attributed paths", () => {
    expect(taskRelations(snapshot, b.id).dependencies).toEqual([a]);
    expect(taskRelations(snapshot, a.id).subsequent).toEqual([b]);
    expect(taskFiles(snapshot, [a.id])).toEqual(["main.py"]);
    expect(taskFiles(snapshot, [b.id])).toEqual([]);
  });
  it("counts actual retry attempts rather than failed tasks", () => {
    expect(retryCount(snapshot)).toBe(0);
    expect(
      retryCount({
        ...snapshot,
        tasks: [
          { ...a, attempt_count: 3 },
          { ...b, status: "FAILED" },
        ],
      }),
    ).toBe(2);
  });
});
it("activity filters combine agent, task, phase, type and status", () => {
  const event = {
    id: "event",
    sequence: 1,
    actor_session_id: "actor",
    task_id: "task",
    phase: "TEST",
    status: "SUCCEEDED",
    event_type: "TASK_COMPLETED",
    occurred_at: "2026-09-10T12:00:00Z",
    payload: {},
  } as Event;
  const filters = {
    actor: "actor",
    task: "task",
    phase: "TEST",
    type: "TASK_COMPLETED",
    status: "SUCCEEDED",
  };
  expect(filterEvents([event], filters)).toEqual([event]);
  expect(filterEvents([event], { ...filters, status: "FAILED" })).toEqual([]);
});
