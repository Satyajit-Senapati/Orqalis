import { useEffect, useState } from "react";
import type { Snapshot } from "./types";
import {
  controlsForRun,
  goalDraftFromSnapshot,
  parseGoalDraft,
  parsePlanDraft,
  planDraftForRun,
  postGovernance,
  type ApprovalRequest,
  type ControlView,
  type PlanDraft,
} from "./governanceApi";

function errorText(failure: unknown): string {
  return failure instanceof Error ? failure.message : String(failure);
}

export function RunGovernance({ snapshot }: { snapshot: Snapshot }) {
  const runId = snapshot.run.id;
  const [controls, setControls] = useState<ControlView | null>(null);
  const [loadingError, setLoadingError] = useState("");
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  // This credential deliberately lives only in React state, never storage or URL.
  const [operatorToken, setOperatorToken] = useState("");
  const [decisionReasons, setDecisionReasons] = useState<Record<string, string>>({});
  const [goalOpen, setGoalOpen] = useState(false);
  const [goalText, setGoalText] = useState("");
  const [goalReason, setGoalReason] = useState("");
  const [planOpen, setPlanOpen] = useState(false);
  const [planText, setPlanText] = useState("");
  const [planDraft, setPlanDraft] = useState<PlanDraft | null>(null);

  useEffect(() => {
    let cancelled = false;
    void controlsForRun(runId)
      .then((view) => {
        if (!cancelled) {
          setControls(view);
          setLoadingError("");
        }
      })
      .catch((failure) => {
        if (!cancelled) setLoadingError(errorText(failure));
      });
    return () => {
      cancelled = true;
    };
  }, [runId, snapshot.last_event_sequence]);

  async function refreshControls() {
    try {
      setControls(await controlsForRun(runId));
      setLoadingError("");
    } catch (failure) {
      setLoadingError(errorText(failure));
    }
  }

  async function action(label: string, work: () => Promise<unknown>, success: string) {
    setBusy(label);
    setActionError("");
    setNotice("");
    try {
      await work();
      setNotice(success);
      await refreshControls();
      return true;
    } catch (failure) {
      setActionError(errorText(failure));
      await refreshControls();
      return false;
    } finally {
      setBusy("");
    }
  }

  async function preview() {
    await action(
      "preview",
      () =>
        postGovernance(
          `/api/runs/${runId}/plan/preview`,
          { idempotency_key: crypto.randomUUID() },
          operatorToken,
        ),
      "Plan preview persisted. Review its tasks and approval request before execution.",
    );
  }

  async function decide(request: ApprovalRequest, decision: "APPROVE" | "REJECT") {
    const reason = decisionReasons[request.id]?.trim() ?? "";
    if (decision === "REJECT" && !reason) {
      setActionError("Give a reason when rejecting an approval request.");
      return;
    }
    await action(
      request.id,
      () =>
        postGovernance(
          `/api/runs/${runId}/approvals/${request.id}/decision`,
          {
            decision,
            expected_subject_digest: request.subject_digest,
            reason,
          },
          operatorToken,
        ),
      `${request.stage} ${decision === "APPROVE" ? "approved" : "rejected"}.`,
    );
  }

  function openGoalEditor() {
    try {
      setGoalText(JSON.stringify(goalDraftFromSnapshot(snapshot), null, 2));
      setGoalReason("");
      setActionError("");
      setGoalOpen(true);
    } catch (failure) {
      setActionError(errorText(failure));
    }
  }

  async function saveGoal() {
    if (!goalReason.trim()) {
      setActionError("A revision reason is required.");
      return;
    }
    let draft;
    try {
      draft = parseGoalDraft(goalText);
    } catch (failure) {
      setActionError(errorText(failure));
      return;
    }
    const saved = await action(
      "goal",
      () =>
        postGovernance(
          `/api/runs/${runId}/goal/revise`,
          {
            goal: draft,
            reason: goalReason.trim(),
            expected_version: snapshot.goal?.goal.version,
          },
          operatorToken,
        ),
      "Goal revision recorded. Approve the new version before planning.",
    );
    if (saved) setGoalOpen(false);
  }

  async function openPlanEditor() {
    setBusy("draft");
    setActionError("");
    try {
      const draft = await planDraftForRun(runId);
      setPlanDraft(draft);
      setPlanText(JSON.stringify(draft, null, 2));
      setPlanOpen(true);
    } catch (failure) {
      setActionError(errorText(failure));
    } finally {
      setBusy("");
    }
  }

  async function savePlan() {
    if (!planDraft || !snapshot.plan) return;
    let edited: PlanDraft;
    try {
      edited = parsePlanDraft(planText, runId, planDraft.version);
    } catch (failure) {
      setActionError(errorText(failure));
      return;
    }
    const saved = await action(
      "plan",
      () =>
        postGovernance(
          `/api/runs/${runId}/plan/replace`,
          {
            plan: edited,
            expected_version: snapshot.run.plan_version,
            idempotency_key: crypto.randomUUID(),
          },
          operatorToken,
        ),
      "Edited plan persisted as a new version. Any earlier plan approval is stale.",
    );
    if (saved) setPlanOpen(false);
  }

  async function replan() {
    await action(
      "replan",
      () =>
        postGovernance(
          `/api/runs/${runId}/plan/replan`,
          { idempotency_key: crypto.randomUUID() },
          operatorToken,
        ),
      "Plan updated for the revised goal. Review and approve before resuming.",
    );
  }

  const isCurrentRequest = (item: ApprovalRequest) =>
    item.stage === "GOAL"
      ? item.subject_version === snapshot.goal?.goal.version
      : item.subject_version === snapshot.run.plan_version;
  const pending =
    controls?.approvals.filter((item) => item.status === "PENDING" && isCurrentRequest(item)) ?? [];
  const history =
    controls?.approvals.filter((item) => item.status !== "PENDING" || !isCurrentRequest(item)) ?? [];
  const canEditGoal = ["GOAL_DEFINED", "PAUSED", "HUMAN_REVIEW_REQUIRED"].includes(
    snapshot.run.state,
  );
  const canEditPlan =
    snapshot.run.state === "PLANNED" ||
    (snapshot.run.state === "PAUSED" && snapshot.run.resume_state === "PLANNED");
  const needsReplan =
    snapshot.goal &&
    snapshot.plan &&
    snapshot.goal.goal.id !== snapshot.plan.goal_version_id &&
    ["PAUSED", "HUMAN_REVIEW_REQUIRED"].includes(snapshot.run.state);

  return (
    <section className="panel governance-panel" aria-label="Run governance">
      <div className="section-heading">
        <div>
          <h2>Operator control</h2>
          <span>Goals, plans, and decisions are persisted by Orqalis Core.</span>
        </div>
        <span className="governance-mode">
          {!controls ? "Loading controls" : controls.policy.mode === "SUPERVISED" ? "Supervised" : "Autonomous"}
        </span>
      </div>
      <div className="governance-body">
        <div className="governance-top">
          <div>
            <strong>Approval gates</strong>
            <p>
              {controls?.policy.gates.length
                ? controls.policy.gates.join(" · ")
                : "No operator gates configured for this run."}
            </p>
          </div>
          <label className="governance-token">
            Operator token
            <input
              type="password"
              autoComplete="off"
              value={operatorToken}
              onChange={(event) => setOperatorToken(event.target.value)}
              placeholder="Paste for approvals and edits"
              aria-label="Operator token"
            />
            <small>Held only until this page closes or reloads.</small>
          </label>
        </div>
        <div className="governance-stage">
          <div>
            <strong>Goal v{snapshot.goal?.goal.version ?? "—"}</strong>
            <p>{snapshot.goal?.goal.goal ?? "Awaiting a versioned goal."}</p>
          </div>
          <div className="governance-actions">
            {canEditGoal && snapshot.goal && (
              <button disabled={!!busy || !operatorToken} onClick={openGoalEditor}>
                Edit goal
              </button>
            )}
            {!canEditGoal && snapshot.run.state === "PLANNED" && (
              <span className="governance-hint">Pause the run to revise its goal.</span>
            )}
            {snapshot.run.state === "GOAL_DEFINED" && (
              <button disabled={!!busy || !operatorToken} onClick={() => void preview()}>
                {busy === "preview" ? "Creating…" : "Preview plan"}
              </button>
            )}
            {needsReplan && (
              <button disabled={!!busy || !operatorToken} onClick={() => void replan()}>
                {busy === "replan" ? "Replanning…" : "Replan revised goal"}
              </button>
            )}
          </div>
        </div>
        <div className="governance-stage">
          <div>
            <strong>Plan v{snapshot.run.plan_version || "—"}</strong>
            <p>
              {snapshot.plan
                ? `${snapshot.plan.tasks.length} tasks · ${snapshot.plan.dependencies.length} dependencies`
                : "Create a plan preview before execution."}
            </p>
          </div>
          {canEditPlan && snapshot.plan && (
            <button disabled={!!busy || !operatorToken} onClick={() => void openPlanEditor()}>
              {busy === "draft" ? "Loading…" : "Edit plan"}
            </button>
          )}
        </div>

        {goalOpen && (
          <div className="governance-editor">
            <div className="governance-editor-heading">
              <strong>Revise goal and acceptance contract</strong>
              <button onClick={() => setGoalOpen(false)}>Close</button>
            </div>
            <p>
              Edit the structured goal, scope, definition of done, and criteria.
              Saving creates a new immutable goal version.
            </p>
            <textarea
              aria-label="Goal draft JSON"
              spellCheck={false}
              value={goalText}
              onChange={(event) => setGoalText(event.target.value)}
            />
            <label>
              Revision reason
              <input
                value={goalReason}
                onChange={(event) => setGoalReason(event.target.value)}
                placeholder="What changed and why?"
              />
            </label>
            <button disabled={!!busy || !operatorToken} onClick={() => void saveGoal()}>
              {busy === "goal" ? "Saving…" : "Save goal revision"}
            </button>
          </div>
        )}
        {planOpen && (
          <div className="governance-editor">
            <div className="governance-editor-heading">
              <strong>Edit plan draft v{planDraft?.version}</strong>
              <button onClick={() => setPlanOpen(false)}>Close</button>
            </div>
            <p>
              Change tasks and dependencies in this fresh draft. Keep its run,
              goal, version, and task IDs. Core validates the DAG and acceptance
              coverage before saving.
            </p>
            <textarea
              aria-label="Plan draft JSON"
              spellCheck={false}
              value={planText}
              onChange={(event) => setPlanText(event.target.value)}
            />
            <button disabled={!!busy || !operatorToken} onClick={() => void savePlan()}>
              {busy === "plan" ? "Saving…" : "Save new plan version"}
            </button>
          </div>
        )}

        <div className="governance-approvals">
          <div className="governance-editor-heading">
            <strong>Approval requests</strong>
            <span>{pending.length} pending</span>
          </div>
          {pending.length === 0 && (
            <p className="governance-hint">No decision is waiting right now.</p>
          )}
          {pending.map((request) => (
            <div className="governance-request" key={request.id}>
              <div className="governance-request-head">
                <strong>{request.stage} · version {request.subject_version}</strong>
                <span className="badge status-pending">Pending</span>
              </div>
              <p>{request.reason || "Review this exact version before continuing."}</p>
              <small className="governance-subject">Subject SHA-256: {request.subject_digest}</small>
              {request.stage === "DELIVERY" && (
                <small>
                  Inspect the delivery policy JSON and Repository Delivery diff before deciding.
                  This card summarizes the policy; it does not display the full policy.
                </small>
              )}
              {request.stage === "TASK" && (
                <small>Inspect the task in the plan and its execution policy before deciding.</small>
              )}
              <label>
                Decision reason
                <input
                  value={decisionReasons[request.id] ?? ""}
                  onChange={(event) =>
                    setDecisionReasons((current) => ({
                      ...current,
                      [request.id]: event.target.value,
                    }))
                  }
                  placeholder="Optional for approval; required for rejection"
                />
              </label>
              <div className="governance-actions">
                <button
                  disabled={!!busy || !operatorToken}
                  onClick={() => void decide(request, "APPROVE")}
                >
                  {busy === request.id ? "Recording…" : "Approve"}
                </button>
                <button
                  className="danger-button"
                  disabled={!!busy || !operatorToken}
                  onClick={() => void decide(request, "REJECT")}
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
          {history.length > 0 && (
            <details className="governance-history">
              <summary>Approval history ({history.length})</summary>
              {history.map((request) => (
                <div className="governance-history-row" key={request.id}>
                  <strong>{request.stage} v{request.subject_version}</strong>
                  <span className={`badge status-${request.status.toLowerCase()}`}>
                    {request.status === "PENDING" ? "SUPERSEDED" : request.status}
                  </span>
                  <small>{request.decision?.reason || request.reason}</small>
                </div>
              ))}
            </details>
          )}
        </div>
        {loadingError && <p role="alert">Controls unavailable: {loadingError}</p>}
        {actionError && <p role="alert">{actionError}</p>}
        {notice && <p role="status">{notice}</p>}
      </div>
    </section>
  );
}
