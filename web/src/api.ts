import { useEffect, useState } from "react";
import type { Event, Snapshot } from "./types";

export class ApiError extends Error {
  constructor(public status: number) {
    super("Orqalis API returned " + status);
  }
}
export class EventBuffer {
  private pending: Event[] = [];
  add(batch: Event[]) {
    this.pending = mergeEvents(this.pending, batch, Number.MAX_SAFE_INTEGER);
  }
  take(cursor: number): Event[] {
    const accepted = this.pending.filter((e) => e.sequence <= cursor);
    this.pending = this.pending.filter((e) => e.sequence > cursor);
    return accepted;
  }
  get size() {
    return this.pending.length;
  }
}
export async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    signal: signal
      ? AbortSignal.any([signal, AbortSignal.timeout(15000)])
      : AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new ApiError(response.status);
  return response.json() as Promise<T>;
}

export function mergeEvents(
  current: Event[],
  incoming: Event[],
  cursor: number,
): Event[] {
  const unique = new Map(current.map((event) => [event.sequence, event]));
  for (const event of incoming)
    if (event.sequence <= cursor) unique.set(event.sequence, event);
  return [...unique.values()]
    .sort((a, b) => a.sequence - b.sequence)
    .slice(-200);
}

export function useRun(runId: string | null) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [connection, setConnection] = useState("Connecting");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    let stopped = false;
    let socket: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const abort = new AbortController();
    const connect = async () => {
      try {
        const state = await get<Snapshot>(`/api/runs/${runId}`, abort.signal);
        const history = await get<Event[]>(
          `/api/runs/${runId}/events?after=${Math.max(0, state.last_event_sequence - 200)}&limit=200`,
          abort.signal,
        );
        if (stopped) return;
        setSnapshot(state);
        setEvents(mergeEvents([], history, state.last_event_sequence));
        setError(null);
        let cursor = state.last_event_sequence;
        const pending = new EventBuffer();
        const protocol = location.protocol === "https:" ? "wss" : "ws";
        socket = new WebSocket(
          `${protocol}://${location.host}/ws/runs/${runId}?after=${cursor}`,
        );
        socket.onopen = () => setConnection("Live");
        socket.onmessage = ({ data }) => {
          try {
            const message = JSON.parse(String(data)) as
              | { type: "events"; events: Event[] }
              | { type: "snapshot"; snapshot: Snapshot };
            if (message.type === "events" && Array.isArray(message.events))
              pending.add(message.events);
            else if (
              message.type === "snapshot" &&
              message.snapshot.last_event_sequence >= cursor
            ) {
              cursor = message.snapshot.last_event_sequence;
              setSnapshot(message.snapshot);
              const batch = pending.take(cursor);
              setEvents((current) => mergeEvents(current, batch, cursor));
            }
          } catch {
            setError("Invalid runtime event frame. Reconnecting.");
            socket?.close();
          }
        };
        socket.onclose = () => {
          if (stopped) return;
          setConnection("Reconnecting");
          retry = setTimeout(() => void connect(), 1500);
        };
        socket.onerror = () => setConnection("Reconnecting");
      } catch (failure) {
        if (stopped) return;
        setError(
          failure instanceof Error ? failure.message : "Connection failed",
        );
        if (
          failure instanceof ApiError &&
          [403, 404, 422].includes(failure.status)
        ) {
          setConnection("Unavailable");
          return;
        }
        setConnection("Offline");
        retry = setTimeout(() => void connect(), 2000);
      }
    };
    void connect();
    return () => {
      stopped = true;
      abort.abort();
      clearTimeout(retry);
      socket?.close();
    };
  }, [runId]);
  return { snapshot, events, connection, error };
}

export function duration(milliseconds: number): string {
  const seconds = Math.floor(Math.max(0, milliseconds) / 1000);
  return `${Math.floor(seconds / 3600)
    .toString()
    .padStart(2, "0")}:${Math.floor((seconds / 60) % 60)
    .toString()
    .padStart(2, "0")}:${(seconds % 60).toString().padStart(2, "0")}`;
}
