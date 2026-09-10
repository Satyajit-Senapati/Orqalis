import { test, expect } from "@playwright/test";
import type { Snapshot } from "../src/types";

const runId = process.env.ORQALIS_E2E_RUN_ID;
test.skip(!runId, "Set ORQALIS_E2E_RUN_ID to a live seeded runtime fixture");

test("Mission Control displays persisted state and survives refresh", async ({ page, request }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`/runs/${runId}`);
  await expect(page.getByRole("heading", { name: "Validate repository behavior" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Orchestrator", exact: true })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("Live");
  await expect(page.getByRole("heading", { name: "tester", exact: true })).toBeVisible();
  const state = await (await request.get(`/api/runs/${runId}`)).json() as Snapshot;
  await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", String(state.plan_completion));
  await expect(page.getByText("Name normalization trims whitespace", { exact: true })).toBeVisible();
  await expect(page.locator(".criterion").first()).toContainText("1 evidence record");
  await page.screenshot({ path: testInfo.outputPath("mission-control-desktop.png"), fullPage: true });
  const before = state.timing.wall_ms;
  await page.reload();
  await expect(page.getByRole("status")).toContainText("Live");
  const after = await (await request.get(`/api/runs/${runId}`)).json() as Snapshot;
  expect(after.timing.wall_ms).toBeGreaterThanOrEqual(before);
  await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", String(state.plan_completion));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: testInfo.outputPath("mission-control-mobile.jpg"), type: "jpeg", quality: 40, fullPage: false });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  expect(errors).toEqual([]);
});
