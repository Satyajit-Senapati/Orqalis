export const label = (value: string) => value.replaceAll("_", " ").toLowerCase();
export const count = (value: number | null | undefined) => value == null ? "Not reported" : value.toLocaleString();
const successStates = new Set(["PASS", "SUCCEEDED", "COMPLETE", "COMPLETED"]);
const failureStates = new Set(["FAIL", "FAILED", "BLOCKED", "CANCELLED"]);
const waitingStates = new Set(["WAITING", "WAITING_FOR_DEPENDENCY", "PAUSED", "HUMAN_REVIEW_REQUIRED"]);
const quietStates = new Set(["PENDING", "IDLE", "AVAILABLE", "LOADED", "SKIPPED"]);

export function statusTone(value: string) {
  const status = value.toUpperCase();
  if (successStates.has(status)) return "success";
  if (failureStates.has(status)) return "failure";
  if (waitingStates.has(status)) return "waiting";
  if (quietStates.has(status)) return "quiet";
  return "active";
}

export const classToken = (value: string) =>
  value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "unknown";

export function Badge({ status }: { status: string }) {
  return <span className={`badge status-${status.toLowerCase()} tone-${statusTone(status)}`}><i />{label(status)}</span>;
}
export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="empty small-empty"><p>{children}</p></div>;
}
