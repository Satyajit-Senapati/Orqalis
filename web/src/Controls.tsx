import { useEffect, useState } from "react";
import type { Snapshot } from "./types";

export function ThemeControl() {
  const [theme, setTheme] = useState(() => localStorage.getItem("orqalis-theme") ?? "system");
  useEffect(() => {
    localStorage.setItem("orqalis-theme", theme);
    const media = matchMedia("(prefers-color-scheme: dark)");
    const apply = () => { document.documentElement.dataset.theme = theme === "system" ? (media.matches ? "dark" : "light") : theme; };
    apply(); media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme]);
  return <label className="theme-control"><span className="sr-only">Color theme</span><select value={theme} onChange={e => setTheme(e.target.value)}>
    <option value="system">System theme</option><option value="dark">Dark theme</option><option value="light">Light theme</option>
  </select></label>;
}
export function RunControls({ snapshot }: { snapshot: Snapshot }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const terminal = ["COMPLETED", "FAILED", "CANCELLED"].includes(snapshot.run.state);
  const suspended = ["PAUSED", "BLOCKED", "HUMAN_REVIEW_REQUIRED"].includes(snapshot.run.state);
  const active = snapshot.attempts.some(a => a.status === "RUNNING");
  async function command(action: string) {
    setBusy(true);
    try {
      const response = await fetch(`/api/runs/${snapshot.run.id}/${action}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idempotency_key: crypto.randomUUID() }),
      });
      if (!response.ok) { const result = await response.json() as { code: string; message?: string }; throw new Error(result.message ?? result.code); }
      setError("");
    } catch (failure) { setError(String(failure)); } finally { setBusy(false); }
  }
  return <div className="run-controls">
    {!terminal && <>{suspended ? <button disabled={busy} onClick={() => void command("resume")}>Resume run</button> :
      <button disabled={busy || active} title={active ? "Pause is available at a worker checkpoint" : "Pause execution"} onClick={() => void command("pause")}>Pause run</button>}
      <button className="danger-button" disabled={busy} onClick={() => void command("cancel")}>Cancel run</button></>}
    {error && <p role="alert">{error}</p>}
  </div>;
}
