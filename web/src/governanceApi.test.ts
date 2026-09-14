import { describe, expect, it, vi } from "vitest";
import {
  goalDraftFromSnapshot,
  parseGoalDraft,
  parsePlanDraft,
  postGovernance,
} from "./governanceApi";
import type { Snapshot } from "./types";

describe("operator control API contracts", () => {
  it("sends the exact approved subject digest and keeps the token out of the body", async () => {
    const fetcher = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        expect(input).toBe("/api/runs/run-1/approvals/request-1/decision");
        expect(init?.method).toBe("POST");
        return new Response(JSON.stringify({ status: "APPROVED" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    );
    const digest = "a".repeat(64);
    const result = await postGovernance<{ status: string }>(
      "/api/runs/run-1/approvals/request-1/decision",
      {
        decision: "APPROVE",
        expected_subject_digest: digest,
        reason: "Reviewed",
      },
      "operator-secret",
      fetcher,
    );
    expect(result.status).toBe("APPROVED");
    const [url, init] = fetcher.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/runs/run-1/approvals/request-1/decision");
    expect(init.headers).toEqual({
      "Content-Type": "application/json",
      "x-orqalis-operator-token": "operator-secret",
    });
    expect(init.signal).toBeInstanceOf(AbortSignal);
    expect(JSON.parse(String(init.body))).toEqual({
      decision: "APPROVE",
      expected_subject_digest: digest,
      reason: "Reviewed",
    });
    expect(String(init.body)).not.toContain("operator-secret");
  });

  it("includes the operator token on plan preview requests", async () => {
    const fetcher = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        expect(input).toBe("/api/runs/run-1/plan/preview");
        expect(init?.method).toBe("POST");
        return new Response("{}", { status: 200 });
      },
    );
    await postGovernance(
      "/api/runs/run-1/plan/preview",
      {
        idempotency_key: "key-1",
      },
      "operator-secret",
      fetcher,
    );
    const [, init] = fetcher.mock.calls[0] as [string, RequestInit];
    expect(init.headers).toEqual({
      "Content-Type": "application/json",
      "x-orqalis-operator-token": "operator-secret",
    });
  });

  it("surfaces Core's structured refusal without inventing an approval result", async () => {
    const fetcher = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            code: "policy_denied",
            message: "Goal approval required",
          }),
          {
            status: 403,
            headers: { "Content-Type": "application/json" },
          },
        ),
    );
    await expect(
      postGovernance("/api/runs/run-1/plan/preview", {}, "", fetcher),
    ).rejects.toThrow("Goal approval required");
  });

  it("builds a new GoalDraft without copying runtime status or evidence", () => {
    const snapshot = {
      goal: {
        goal: {
          id: "goal-1",
          version: 1,
          goal: "Update source",
          scope: ["main.py"],
          out_of_scope: ["vendor"],
          constraints: ["Keep API"],
          assumptions: [],
          definition_of_done: ["Tests pass"],
        },
        criteria: [
          {
            id: "criterion-1",
            key: "AC-1",
            description: "Source exists",
            priority: "required",
            validation_spec: { kind: "file", path: "main.py" },
            status: "PASS",
            evidence_refs: ["evidence-1"],
            attempt_count: 1,
          },
        ],
      },
    } as unknown as Snapshot;
    const draft = goalDraftFromSnapshot(snapshot);
    expect(draft.criteria[0]).toEqual({
      key: "AC-1",
      description: "Source exists",
      priority: "required",
      validation_spec: { kind: "file", path: "main.py" },
    });
    expect(JSON.stringify(draft)).not.toContain("evidence-1");
    expect(parseGoalDraft(JSON.stringify(draft))).toEqual(draft);
  });

  it("rejects a pasted plan from another run or version before posting", () => {
    const plan = { run_id: "other", version: 2, tasks: [], dependencies: [] };
    expect(() => parsePlanDraft(JSON.stringify(plan), "run-1", 2)).toThrow(
      "do not match this draft",
    );
    plan.run_id = "run-1";
    expect(() => parsePlanDraft(JSON.stringify(plan), "run-1", 3)).toThrow(
      "do not match this draft",
    );
  });
});
