import { chromium, expect } from "@playwright/test";
import { readFile, mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../..");
const fixture = async (name) =>
  JSON.parse(await readFile(resolve(root, ".tools", name), "utf8"));
const active = (await fixture("ui-fixture.json")).run_id;
const completed = (await fixture("ui-completed.json")).run_id;
const repair = (await fixture("ui-repair.json")).run_id;
const base = process.env.ORQALIS_UI_URL || "http://127.0.0.1:7842";
const output = resolve(root, "docs/assets");
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
  channel:
    process.env.ORQALIS_BROWSER_CHANNEL === "chromium" ? undefined : "chrome",
  headless: true,
});
const page = await browser.newPage({
  viewport: { width: 1600, height: 1180 },
  deviceScaleFactor: 1,
});
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
async function run(id) {
  await page.goto(base + "/runs/" + id);
  await page.getByRole("tab", { name: "Mission", exact: true }).waitFor();
  await page.getByLabel("Color theme").selectOption("dark");
  await expect(page.getByRole("status")).toContainText("Live");
}
async function view(name) {
  await page.getByRole("tab", { name, exact: true }).click();
  await page.getByRole("tabpanel").scrollIntoViewIfNeeded();
}
async function capture(name) {
  await page.screenshot({
    path: resolve(output, name + ".jpg"),
    type: "jpeg",
    quality: 78,
    animations: "disabled",
  });
}
try {
  await run(active);
  await capture("mission-control");
  await run(completed);
  await view("Graph");
  await expect(page.locator(".react-flow__node")).toHaveCount(9);
  await capture("orchestration-graph");
  await page.getByRole("tab", { name: "Agents", exact: true }).click();
  await page
    .locator(".agent-directory .actor-row")
    .filter({ hasText: "developer" })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toContainText("Context:");
  await capture("agent-inspector");
  await page.keyboard.press("Escape");
  await view("Timeline");
  await expect(page.locator(".timeline-bar").first()).toBeVisible();
  await capture("execution-timeline");
  await view("Project Brain");
  await expect(page.locator(".memory-card").first()).toBeVisible();
  await capture("project-memory");
  await view("Skills");
  await expect(page.locator(".skill-card")).toHaveCount(3);
  await capture("skills");
  await view("Delivery");
  await page.getByRole("button", { name: "main.py", exact: true }).click();
  await expect(page.locator(".diff-view")).toContainText(
    "value.strip().lower()",
  );
  await capture("repository-delivery");
  await run(repair);
  await view("Acceptance");
  await page
    .locator(".evidence-criterion")
    .first()
    .locator("summary")
    .first()
    .click();
  await page.getByText("Review history", { exact: false }).click();
  await capture("verification-repair");
  if (errors.length) throw new Error(errors.join("\n"));
  console.log("Captured eight real persisted runtime views in docs/assets.");
} finally {
  await browser.close();
}
