import { describe, expect, it } from "vitest";
import { duration, mergeEvents } from "./api";
import type { Event } from "./types";

const event = (sequence: number): Event => ({ id: String(sequence), sequence, event_type: "TASK_STARTED",
  occurred_at: "2026-09-10T12:00:00Z", actor_session_id: null, task_id: null, payload: {} });
describe("durable event reconciliation", () => {
  it("deduplicates reconnect replay and excludes events newer than the snapshot", () => {
    expect(mergeEvents([event(1), event(2)], [event(4), event(2), event(3)], 3).map((item) => item.sequence))
      .toEqual([1, 2, 3]);
  });
  it("keeps ordering while bounding presentation history", () => {
    const history = mergeEvents([], Array.from({ length: 240 }, (_, index) => event(240 - index)), 240);
    expect(history).toHaveLength(200);
    expect(history[0].sequence).toBe(41);
    expect(history[199].sequence).toBe(240);
  });
  it("formats persisted durations without running a browser clock", () => {
    expect(duration(3661000)).toBe("01:01:01");
    expect(duration(-1000)).toBe("00:00:00");
  });
});
