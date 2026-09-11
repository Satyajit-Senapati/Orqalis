import { useEffect, useState } from "react";
import type { Snapshot } from "./types";

type RunCommand = "pause" | "resume" | "cancel";
type ThemePreference = "system" | "dark" | "light";
type Fetcher = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

interface CommandOptions {
  fetcher?: Fetcher;
  timeoutMs?: number;
}

export function readThemePreference(
  storage?: Pick<Storage, "getItem">,
): ThemePreference {
  try {
    const value = (storage ?? globalThis.localStorage).getItem("orqalis-theme");
    return value === "system" || value === "light" || value === "dark"
      ? value
      : "dark";
  } catch {
    return "dark";
  }
}

function persistThemePreference(theme: ThemePreference): void {
  try {
    globalThis.localStorage.setItem("orqalis-theme", theme);
  } catch {
    // Storage can be unavailable in restricted browser contexts; the theme still applies.
  }
}

async function responseError(response: Response): Promise<string> {
  const fallback = "Orqalis API returned " + response.status;
  let text: string;
  try {
    text = (await response.text()).trim();
  } catch {
    return fallback;
  }
  if (!text) return fallback;
  try {
    const body = JSON.parse(text) as unknown;
    if (typeof body === "string") return body;
    if (body && typeof body === "object") {
      const record = body as Record<string, unknown>;
      const details = [record.message, record.detail, record.code]
        .filter(
          (value): value is string => typeof value === "string" && !!value,
        )
        .filter((value, index, values) => values.indexOf(value) === index);
      if (details.length) return details.join(" · ");
    }
  } catch {
    return text;
  }
  return fallback;
}

export async function postRunCommand(
  runId: string,
  action: RunCommand,
  { fetcher = fetch, timeoutMs = 15_000 }: CommandOptions = {},
): Promise<void> {
  const controller = new AbortController();
  const seconds = timeoutMs / 1000;
  const timeoutError = new Error(
    `Orqalis did not respond within ${seconds} ${seconds === 1 ? "second" : "seconds"}.`,
  );
  const timeout = globalThis.setTimeout(
    () => controller.abort(timeoutError),
    timeoutMs,
  );
  try {
    const response = await fetcher("/api/runs/" + runId + "/" + action, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idempotency_key: crypto.randomUUID() }),
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(await responseError(response));
  } catch (failure) {
    if (controller.signal.aborted && controller.signal.reason === timeoutError)
      throw timeoutError;
    throw failure;
  } finally {
    globalThis.clearTimeout(timeout);
  }
}

export function ThemeControl() {
  const [theme, setTheme] = useState<ThemePreference>(readThemePreference);
  useEffect(() => {
    persistThemePreference(theme);
    const media = matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const resolved =
        theme === "system" ? (media.matches ? "dark" : "light") : theme;
      document.documentElement.dataset.theme = resolved;
      document
        .querySelector<HTMLMetaElement>('meta[name="theme-color"]')
        ?.setAttribute("content", resolved === "dark" ? "#07070f" : "#eef3f6");
    };
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme]);
  return (
    <label className="theme-control">
      <span className="sr-only">Color theme</span>
      <select
        value={theme}
        onChange={(e) => setTheme(e.target.value as ThemePreference)}
      >
        <option value="system">System theme</option>
        <option value="dark">Dark theme</option>
        <option value="light">Light theme</option>
      </select>
    </label>
  );
}
export function RunControls({ snapshot }: { snapshot: Snapshot }) {
  const [error, setError] = useState("");
  const [busyAction, setBusyAction] = useState<RunCommand | null>(null);
  const terminal = ["COMPLETED", "FAILED", "CANCELLED"].includes(
    snapshot.run.state,
  );
  const suspended = ["PAUSED", "BLOCKED", "HUMAN_REVIEW_REQUIRED"].includes(
    snapshot.run.state,
  );
  const active = snapshot.attempts.some((a) => a.status === "RUNNING");
  async function command(action: RunCommand) {
    if (
      action === "cancel" &&
      !globalThis.confirm(
        "Cancel this run? The current workflow will stop and the cancellation will be persisted.",
      )
    )
      return;
    setBusyAction(action);
    try {
      await postRunCommand(snapshot.run.id, action);
      setError("");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusyAction(null);
    }
  }
  const progress = busyAction
    ? (busyAction === "pause"
        ? "Pausing"
        : busyAction === "resume"
          ? "Resuming"
          : "Cancelling") + " run…"
    : "";
  return (
    <div className="run-controls" aria-busy={busyAction !== null}>
      <span className="run-repair">
        Repair loop{" "}
        <strong>
          {snapshot.run.repair_iteration} / {snapshot.run.max_repair_iterations}
        </strong>
      </span>
      {!terminal && (
        <>
          {suspended ? (
            <button
              disabled={busyAction !== null}
              onClick={() => void command("resume")}
            >
              {busyAction === "resume" ? "Resuming…" : "Resume run"}
            </button>
          ) : (
            <button
              disabled={busyAction !== null || active}
              title={
                active
                  ? "Pause is available at a worker checkpoint"
                  : "Pause execution"
              }
              onClick={() => void command("pause")}
            >
              {busyAction === "pause" ? "Pausing…" : "Pause run"}
            </button>
          )}
          <button
            className="danger-button"
            disabled={busyAction !== null}
            onClick={() => void command("cancel")}
          >
            {busyAction === "cancel" ? "Cancelling…" : "Cancel run"}
          </button>
        </>
      )}
      {progress && (
        <span className="command-progress" role="status" aria-live="polite">
          {progress}
        </span>
      )}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
