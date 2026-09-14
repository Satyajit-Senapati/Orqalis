import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { Snapshot } from "../src/types";
import type { ControlView, PlanDraft } from "../src/governanceApi";

const fixtureRunId = process.env.ORQALIS_E2E_RUN_ID;
const operatorToken = process.env.ORQALIS_E2E_OPERATOR_TOKEN;

test.skip(
  !fixtureRunId || !operatorToken,
  "Requires a persisted run fixture and dedicated ORQALIS_E2E_OPERATOR_TOKEN matching the local API",
);

test("supervised run decisions and plan edits stay bound to persisted versions", async ({
  page,
  request,
}) => {
  const fixture = (await (
    await request.get(`/api/runs/${fixtureRunId}`)
  ).json()) as Snapshot;
  const created = await request.post("/api/runs", {
    data: {
      project_id: fixture.run.project_id,
      request: "Review name normalization with operator gates",
      branch: `feature/browser-governance-${randomUUID().slice(0, 8)}`,
      mode: "SUPERVISED",
      goal: {
        goal: "Review name normalization with operator gates",
        scope: ["main.py"],
        constraints: ["Preserve unrelated files"],
        definition_of_done: ["Name normalization is inspected against source"],
        criteria: [
          {
            key: "AC-1",
            description: "Name normalization trims whitespace",
            validation_spec: {
              kind: "file",
              path: "main.py",
              contains: "value.strip()",
            },
          },
        ],
      },
    },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  const initial = (await created.json()) as Snapshot;
  const runId = initial.run.id;
  const controlsUrl = `/api/runs/${runId}/controls`;
  const initialControls = (await (
    await request.get(controlsUrl)
  ).json()) as ControlView;
  expect(initialControls.policy.mode).toBe("SUPERVISED");
  expect(initialControls.approvals).toEqual([]);

  await page.goto(`/runs/${runId}`);
  const governance = page.getByRole("region", { name: "Run governance" });
  await expect(governance.getByText("Supervised", { exact: true })).toBeVisible();
  await governance.getByLabel("Operator token").fill(operatorToken!);
  await governance.getByRole("button", { name: "Preview plan" }).click();
  await expect(governance.getByText("GOAL \u00b7 version 1")).toBeVisible();
  await expect(governance.getByRole("alert")).toContainText("approval");
  await governance.getByRole("button", { name: "Reject" }).click();
  await expect(governance.getByRole("alert")).toContainText(
    "Give a reason when rejecting",
  );
  await governance.getByRole("button", { name: "Approve" }).click();
  await expect(governance.getByRole("status")).toContainText("GOAL approved");
  await expect(governance.getByRole("button", { name: "Approve" })).toHaveCount(0);

  await governance.getByRole("button", { name: "Preview plan" }).click();
  await expect(governance.getByText("PLAN \u00b7 version 1")).toBeVisible();
  await expect(governance.getByText("Plan v1")).toBeVisible();
  await governance.getByRole("button", { name: "Edit plan" }).click();
  const planEditor = governance.getByLabel("Plan draft JSON");
  const draft = JSON.parse(await planEditor.inputValue()) as PlanDraft;
  expect(draft.version).toBe(2);
  expect(draft.tasks.length).toBeGreaterThan(0);
  draft.tasks[0].description = "Inspect normalization with an operator-reviewed plan";
  await planEditor.fill(JSON.stringify(draft, null, 2));
  await governance.getByRole("button", { name: "Save new plan version" }).click();
  await expect(governance.getByText("PLAN \u00b7 version 2")).toBeVisible();
  await expect(governance.getByText("Plan v2")).toBeVisible();
  await expect(governance.getByRole("button", { name: "Approve" })).toHaveCount(1);
  await expect(governance.getByText("PLAN \u00b7 version 1")).toHaveCount(0);
  await governance.getByText("Approval history (2)").click();
  await expect(governance.getByText("PLAN v1")).toBeVisible();
  await expect(governance.getByText("SUPERSEDED")).toBeVisible();

  const latestControls = (await (
    await request.get(controlsUrl)
  ).json()) as ControlView;
  expect(latestControls.approvals.at(-1)).toEqual(
    expect.objectContaining({ stage: "PLAN", subject_version: 2, status: "PENDING" }),
  );
  const persisted = (await (
    await request.get(`/api/runs/${runId}`)
  ).json()) as Snapshot;
  expect(persisted.run.plan_version).toBe(2);
  expect(persisted.plan?.tasks.some((task) => task.description === draft.tasks[0].description)).toBe(true);

  await page.reload();
  await expect(governance.getByLabel("Operator token")).toHaveValue("");
  await expect(governance.getByRole("button", { name: "Approve" })).toBeDisabled();
  await expect(governance.getByText("PLAN \u00b7 version 2")).toBeVisible();
});
