import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import type { Snapshot } from "../src/types";

const snapshot = JSON.parse(readFileSync(new URL("../src/fixtures/runtime-trace.json", import.meta.url), "utf8")) as Snapshot;

test("saved actual parallel-repair snapshot supports keyboard trace ancestry and critical path", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/projects") return route.fulfill({ json: [{ id: snapshot.run.project_id, name: "Trace fixture", repo_root: "/fixture", default_branch: "main" }] });
    if (path === "/api/runs") return route.fulfill({ json: [snapshot.run] });
    if (path === `/api/runs/${snapshot.run.id}`) return route.fulfill({ json: snapshot });
    if (path.endsWith("/events")) return route.fulfill({ json: [] });
    return route.fulfill({ status: 404, json: { message: "Unrelated fixture endpoint" } });
  });
  await page.routeWebSocket("**/ws/runs/**", (socket) => {
    socket.send(JSON.stringify({ type: "snapshot", snapshot }));
  });
  await page.goto(`/runs/${snapshot.run.id}`);
  await page.getByRole("tab", { name: "Timeline", exact: true }).click();
  await expect(page.getByLabel("Measured critical path")).toContainText("recorded work");
  await expect(page.locator(".critical-path-bar").first()).toBeVisible();
  const panel = page.getByRole("region", { name: "Local operation trace" });
  await panel.getByLabel("Trace operation type").selectOption("tool");
  await expect(panel.locator("tbody tr")).toHaveCount(snapshot.tools.length);
  const operation = panel.locator("tbody tr").first().locator("td").first().getByRole("button");
  await operation.focus();
  await page.keyboard.press("Enter");
  await expect(operation).toHaveAttribute("aria-pressed", "true");
  const inspector = panel.locator(".detail-card");
  const tool = snapshot.trace!.find((node) => node.kind === "tool")!;
  await expect(inspector).toContainText(tool.id);
  await expect(inspector).toContainText(tool.task_execution_id!);
  await expect(inspector).toContainText("fixture /");
  const ancestry = panel.getByRole("navigation", { name: "Operation ancestry" });
  await expect(ancestry.getByRole("button").first()).toHaveText("Run");
  await ancestry.getByRole("button", { name: "Model call", exact: true }).click();
  await expect(inspector).toContainText(tool.parent_id!);
  await expect(inspector).not.toContainText(tool.id);
  await panel.getByLabel("Trace operation type").selectOption("task");
  await expect(panel.locator("tbody tr")).toHaveCount(snapshot.attempts.length);
  await page.setViewportSize({ width: 390, height: 844 });
  await panel.getByLabel("Trace operation type").scrollIntoViewIfNeeded();
  await expect(panel.getByLabel("Trace operation type")).toBeInViewport();
  await page.screenshot({ path: info.outputPath("trace-mobile.jpg"), type: "jpeg", quality: 70 });
  expect(errors).toEqual([]);
});
