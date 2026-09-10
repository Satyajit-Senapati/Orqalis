import { describe, expect, it } from "vitest";
import { duration, mergeEvents, EventBuffer } from "./api";
import type { Event } from "./types";

const event = (sequence: number): Event => ({
  id: String(sequence),
  sequence,
  event_type: "TASK_STARTED",
  occurred_at: "2026-09-10T12:00:00Z",
  actor_session_id: null,
  task_id: null,
  payload: {},
});
describe("durable event reconciliation", () => {
  it("deduplicates reconnect replay and excludes events newer than the snapshot", () => {
    expect(
      mergeEvents([event(1), event(2)], [event(4), event(2), event(3)], 3).map(
        (item) => item.sequence,
      ),
    ).toEqual([1, 2, 3]);
  });
  it("keeps ordering while bounding presentation history", () => {
    const history = mergeEvents(
      [],
      Array.from({ length: 240 }, (_, index) => event(240 - index)),
      240,
    );
    expect(history).toHaveLength(200);
    expect(history[0].sequence).toBe(41);
    expect(history[199].sequence).toBe(240);
  });
  it("formats persisted durations without running a browser clock", () => {
    expect(duration(3661000)).toBe("01:01:01");
    expect(duration(-1000)).toBe("00:00:00");
  });
});

it("bounds events during long reconnect backlogs and retains future frames", () => {
  const buffer = new EventBuffer();
  for (let sequence = 1; sequence <= 10000; sequence += 100) {
    buffer.add(
      Array.from({ length: 100 }, (_, index) => event(sequence + index)),
    );
    expect(buffer.size).toBeLessThanOrEqual(200);
  }
  const accepted = buffer.take(9950);
  expect(accepted.at(-1)?.sequence).toBe(9950);
  expect(buffer.size).toBe(50);
  expect(buffer.take(10000)).toHaveLength(50);
  expect(buffer.size).toBe(0);
});
