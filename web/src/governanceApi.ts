import { get } from "./api";
import type { Criterion, Snapshot } from "./types";

export type ApprovalStage = "GOAL" | "PLAN" | "TASK" | "REPAIR" | "DELIVERY";
export type ApprovalStatus = "PENDING" | "APPROVED" | "REJECTED";

export interface ApprovalRequest {
  id: string;
  run_id: string;
  stage: ApprovalStage;
  subject_version: number;
  subject_digest: string;
  reason: string;
  status: ApprovalStatus;
  created_at: string;
  decision: {
    decision: "APPROVE" | "REJECT";
    actor: string;
    reason: string;
    created_at: string;
  } | null;
}

export interface ControlView {
  policy: {
    run_id: string;
    mode: "AUTONOMOUS" | "SUPERVISED";
    gates: ApprovalStage[];
  };
  approvals: ApprovalRequest[];
}

export interface GoalDraft {
  goal: string;
  scope: string[];
  out_of_scope: string[];
  constraints: string[];
  assumptions: string[];
  definition_of_done: string[];
  criteria: {
    key: string;
    description: string;
    priority: string;
    validation_spec: Criterion["validation_spec"];
  }[];
}

export interface PlanDraft {
  run_id: string;
  goal_version_id: string;
  version: number;
  tasks: {
    id: string;
    description: string;
    expected_outcome: string;
    preferred_role: string;
    validation_method: string;
    [key: string]: unknown;
  }[];
  dependencies: {
    task_id: string;
    depends_on_task_id: string;
    dependency_type: string;
  }[];
}

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export function goalDraftFromSnapshot(snapshot: Snapshot): GoalDraft {
  if (!snapshot.goal) throw new Error("This run has no goal to revise.");
  const { goal, criteria } = snapshot.goal;
  return {
    goal: goal.goal,
    scope: goal.scope,
    out_of_scope: goal.out_of_scope ?? [],
    constraints: goal.constraints,
    assumptions: goal.assumptions ?? [],
    definition_of_done: goal.definition_of_done,
    criteria: criteria.map((item) => ({
      key: item.key,
      description: item.description,
      priority: item.priority,
      validation_spec: item.validation_spec,
    })),
  };
}

export async function controlsForRun(runId: string): Promise<ControlView> {
  return get<ControlView>(`/api/runs/${runId}/controls`);
}

export async function planDraftForRun(runId: string): Promise<PlanDraft> {
  return get<PlanDraft>(`/api/runs/${runId}/plan/draft`);
}

export async function postGovernance<T>(
  path: string,
  body: unknown,
  token = "",
  fetcher: Fetcher = fetch,
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["x-orqalis-operator-token"] = token;
  const response = await fetcher(path, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(15_000),
  });
  if (!response.ok) {
    let message = `Orqalis API returned ${response.status}`;
    try {
      const detail = (await response.json()) as {
        message?: unknown;
        detail?: unknown;
      };
      if (typeof detail.message === "string") message = detail.message;
      else if (typeof detail.detail === "string") message = detail.detail;
    } catch {
      // Keep the HTTP status when an intermediary returns a non-JSON error.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function parseGoalDraft(text: string): GoalDraft {
  const value: unknown = JSON.parse(text);
  if (!value || typeof value !== "object") throw new Error("Goal must be a JSON object.");
  const goal = value as GoalDraft;
  if (
    typeof goal.goal !== "string" ||
    !Array.isArray(goal.scope) ||
    !Array.isArray(goal.definition_of_done) ||
    !Array.isArray(goal.criteria)
  ) {
    throw new Error("Goal needs text, scope, definition of done, and criteria.");
  }
  return goal;
}

export function parsePlanDraft(text: string, runId: string, version: number): PlanDraft {
  const value: unknown = JSON.parse(text);
  if (!value || typeof value !== "object") throw new Error("Plan must be a JSON object.");
  const plan = value as PlanDraft;
  if (
    plan.run_id !== runId ||
    plan.version !== version ||
    !Array.isArray(plan.tasks) ||
    !Array.isArray(plan.dependencies)
  ) {
    throw new Error("Plan run, version, tasks, or dependencies do not match this draft.");
  }
  return plan;
}
