import type { Actor, Snapshot, Task } from "./types";
export type Selection = { kind: "actor" | "task"; id: string } | null;
export type Inspect = (selection: Selection) => void;
export const visibleTasks = (s: Snapshot): Task[] =>
  s.plan?.tasks ?? s.preparation_tasks;
export const actorName = (a: Actor) =>
  a.session.actor_type === "ORCHESTRATOR"
    ? "Orchestrator"
    : (a.session.role?.replaceAll("_", " ") ?? "agent");
export const retryCount = (s: Snapshot) =>
  s.tasks.reduce((sum, task) => sum + Math.max(0, task.attempt_count - 1), 0);
export function taskRelations(s: Snapshot, id: string) {
  const edges = s.plan?.dependencies ?? [];
  return {
    dependencies: edges
      .filter((e) => e.task_id === id)
      .map((e) => s.tasks.find((t) => t.id === e.depends_on_task_id))
      .filter((t): t is Task => !!t),
    subsequent: edges
      .filter((e) => e.depends_on_task_id === id)
      .map((e) => s.tasks.find((t) => t.id === e.task_id))
      .filter((t): t is Task => !!t),
  };
}
export function nextWork(s: Snapshot): string {
  if (s.run.state === "COMPLETED")
    return "Delivered. Accepted knowledge is available to future runs.";
  if (["CANCELLED", "FAILED"].includes(s.run.state))
    return "This run has ended. Inspect its recorded outcome.";
  if (["PAUSED", "BLOCKED", "HUMAN_REVIEW_REQUIRED"].includes(s.run.state))
    return "Execution is suspended. Resolve the blocker before resuming.";
  const tasks = visibleTasks(s);
  const running = tasks.filter((t) => t.status === "RUNNING");
  if (running.length) return running.map((t) => t.description).join(" · ");
  const ready = tasks.filter((t) => t.status === "READY");
  if (ready.length)
    return "Ready for dispatch: " + ready.map((t) => t.description).join(" · ");
  return "Waiting for the next Core checkpoint. No task is currently ready.";
}
export function taskFiles(s: Snapshot, taskIds: string[]): string[] {
  return [
    ...new Set([
      ...s.artifacts
        .filter((a) => a.task_id && taskIds.includes(a.task_id))
        .map((a) => a.path_or_uri),
      ...s.evidence
        .filter(
          (e) =>
            e.task_id &&
            taskIds.includes(e.task_id) &&
            e.structured_data.source_ref,
        )
        .map((e) => e.structured_data.source_ref!),
    ]),
  ];
}
