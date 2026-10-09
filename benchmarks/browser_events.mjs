import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";
const [repository, base, runId, initialState, output, chromePath, repetitions = "3"] = process.argv.slice(2);
const { chromium } = createRequire(resolve(repository, "web/package.json"))("@playwright/test");
const browser = await chromium.launch({ executablePath: chromePath, headless: true });
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.addInitScript(() => {
    window.measuredSnapshots = [];
    window.measuredEvents = [];
    window.measuredSockets = [];
    const Native = window.WebSocket;
    window.WebSocket = class extends Native {
      constructor(...args) {
        super(...args);
        const connection = { id: window.measuredSockets.length + 1, opened: null, closed: null, code: null, error: false };
        window.measuredSockets.push(connection);
        this.addEventListener("open", () => { connection.opened = performance.now(); });
        this.addEventListener("close", event => { connection.closed = performance.now(); connection.code = event.code; });
        this.addEventListener("error", () => { connection.error = true; });
        this.addEventListener("message", event => {
          const message = JSON.parse(event.data);
          const at = performance.now();
          if (message.type === "snapshot") {
            const snapshot = message.snapshot;
            window.measuredSnapshots.push({ run_id: snapshot.run.id,
              state: snapshot.run.state, sequence: snapshot.last_event_sequence, at });
          }
          if (message.type === "events") {
            window.measuredEvents.push(...message.events.map(item => ({ ...item, at })));
          }
        });
      }
    };
  });
  await page.goto(`${base}/runs/${runId}`);
  await page.locator(`.page-heading > .status-${initialState.toLowerCase()}`).waitFor();
  await page.waitForFunction(id => window.measuredSnapshots.some(item => item.run_id === id), runId);
  const samples = [];
  for (let repeat = 0; repeat < Number(repetitions); repeat++) {
    for (const [action, expected] of [["pause", "PAUSED"], ["resume", initialState]]) {
      const sample = await page.evaluate(async ({ runId, action, expected }) => {
        const before = Math.max(...window.measuredSnapshots.filter(item => item.run_id === runId).map(item => item.sequence));
        const commandKey = crypto.randomUUID();
        const start = performance.now();
        const domObservations = [];
        const observe = () => {
          if (!document.querySelector(`.page-heading > .status-${expected.toLowerCase()}`)) return;
          const match = document.querySelector(".run-footer")?.textContent.match(/sequence\s+(\d+)/);
          if (match) domObservations.push({ sequence: Number(match[1]), at: performance.now() });
        };
        const observer = new MutationObserver(observe);
        observer.observe(document.body, { subtree: true, childList: true, attributes: true, characterData: true });
        try {
          const response = await fetch(`/api/runs/${runId}/${action}`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ idempotency_key: commandKey })
          });
          if (!response.ok) throw new Error(`Action failed: ${response.status}`);
          const persisted = await response.json();
          const responded = performance.now();
          if (persisted.id !== runId || persisted.state !== expected || persisted.last_event_sequence <= before) {
            throw new Error("Unexpected persisted run/state/cursor");
          }
          const expectedType = action === "pause" ? "RUN_PAUSED" : "RUN_RESUMED";
          const deadline = performance.now() + 10000;
          while (performance.now() < deadline) {
            const snapshot = window.measuredSnapshots.find(item => item.at >= start &&
              item.run_id === runId && item.state === expected && item.sequence === persisted.last_event_sequence);
            const event = window.measuredEvents.find(item => item.at >= start && item.run_id === runId &&
              item.idempotency_key === `${commandKey}:run` && item.event_type === expectedType &&
              item.sequence > before && item.sequence <= persisted.last_event_sequence);
            const dom = domObservations.find(item => item.sequence === persisted.last_event_sequence);
            if (snapshot && event && dom) {
              if (dom.at < snapshot.at || location.pathname !== `/runs/${runId}`) {
                throw new Error("DOM lacks the same run/snapshot witness");
              }
              return { action, expected, run_id: runId, command_key: commandKey,
                persisted_run_id: persisted.id, persisted_state: persisted.state,
                before_sequence: before, persisted_sequence: persisted.last_event_sequence,
                event_id: event.id, event_run_id: event.run_id, event_type: event.event_type,
                event_key: event.idempotency_key, event_sequence: event.sequence,
                snapshot_run_id: snapshot.run_id, snapshot_sequence: snapshot.sequence,
                dom_run_id: runId, dom_sequence: dom.sequence,
                request_to_http_ms: responded - start, request_to_snapshot_ms: snapshot.at - start,
                request_to_event_ms: event.at - start, request_to_dom_ms: dom.at - start,
                snapshot_to_dom_ms: dom.at - snapshot.at };
            }
            await new Promise(resolve => setTimeout(resolve, 10));
          }
          throw new Error("Missing correlated command/event/snapshot/DOM witness: " + JSON.stringify({
            run_id: runId, action, command_key: commandKey, before,
            persisted_sequence: persisted.last_event_sequence, expected,
            snapshots: window.measuredSnapshots.filter(item => item.run_id === runId && item.at >= start).slice(-4),
            events: window.measuredEvents.filter(item => item.idempotency_key === `${commandKey}:run`).slice(-2),
            dom: domObservations.slice(-4),
            route: location.pathname,
            sockets: window.measuredSockets.slice(-4),
            connection: document.querySelector(".connection")?.textContent,
            footer: document.querySelector(".run-footer")?.textContent.slice(0, 200)
          }));
        } finally { observer.disconnect(); }
      }, { runId, action, expected });
      samples.push(sample);
    }
  }
  if (errors.length) throw new Error(errors.join("; "));
  await writeFile(output, JSON.stringify({ run_id: runId, initial_state: initialState,
    samples, page_errors: errors, browser: browser.version() }, null, 2) + "\n");
} finally { await browser.close(); }
