import { randomUUID } from "node:crypto";
import { cp, mkdir, readFile, rename, rm, stat } from "node:fs/promises";
import { resolve } from "node:path";
import { chromium, expect } from "@playwright/test";

const root = resolve(import.meta.dirname, "../..");
const pointer = async (name) =>
  JSON.parse(await readFile(resolve(root, ".tools", name), "utf8"));
const active = (await pointer("ui-fixture.json")).run_id;
const completed = (await pointer("ui-completed.json")).run_id;
const repair = (await pointer("ui-repair.json")).run_id;
const base = process.env.ORQALIS_UI_URL || "http://127.0.0.1:7842";
const baseOrigin = new URL(base).origin;
const output = resolve(root, "docs", "assets");
const temporaryRoot = resolve(root, ".tools");
const staging = resolve(temporaryRoot, "dashboard-capture-" + randomUUID());
const screenshotNames = [
  "workspace-overview",
  "mission-control",
  "orchestration-graph",
  "agent-inspector",
  "execution-timeline",
  "project-memory",
  "skills",
  "repository-delivery",
  "verification-repair",
];
const captured = new Set();
await mkdir(temporaryRoot, { recursive: true });
try {
  if (await stat(output).catch(() => null))
    await cp(output, staging, { recursive: true });
  else await mkdir(staging, { recursive: true });
} catch (error) {
  await rm(staging, { recursive: true, force: true });
  throw error;
}

const browser = await chromium
  .launch({
    channel:
      process.env.ORQALIS_BROWSER_CHANNEL === "chromium"
        ? undefined
        : process.env.ORQALIS_BROWSER_CHANNEL || "chrome",
    headless: true,
  })
  .catch(async (error) => {
    await rm(staging, { recursive: true, force: true });
    throw error;
  });
const page = await browser
  .newPage({
    viewport: { width: 1600, height: 1180 },
    deviceScaleFactor: 1,
  })
  .catch(async (error) => {
    await browser.close();
    await rm(staging, { recursive: true, force: true });
    throw error;
  });
const diagnostics = [];
const sameOrigin = (url) => {
  try {
    return new URL(url).origin === baseOrigin;
  } catch {
    return false;
  }
};
page.on("pageerror", (error) =>
  diagnostics.push("pageerror: " + error.message),
);
page.on("console", (message) => {
  if (message.type() === "error") {
    const location = message.location();
    diagnostics.push(
      "console.error: " +
        message.text() +
        (location.url
          ? " @ " + location.url + ":" + (location.lineNumber + 1)
          : ""),
    );
  }
});
page.on("requestfailed", (request) => {
  if (sameOrigin(request.url()))
    diagnostics.push(
      "requestfailed: " +
        request.method() +
        " " +
        request.url() +
        " (" +
        (request.failure()?.errorText || "unknown") +
        ")",
    );
});
page.on("response", (response) => {
  const url = new URL(response.url());
  if (url.origin === baseOrigin && response.status() >= 400)
    diagnostics.push(
      (url.pathname.startsWith("/api/") ? "API " : "") +
        "HTTP " +
        response.status() +
        ": " +
        url.pathname,
    );
});

async function settleLayout() {
  await page.evaluate(async () => {
    await globalThis.document.fonts.ready;
    await new Promise((done) =>
      globalThis.requestAnimationFrame(() =>
        globalThis.requestAnimationFrame(done),
      ),
    );
  });
  await page.waitForTimeout(75);
}

async function assertPitchSurface(runSurface = true) {
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator(".shell")).toBeVisible();
  if (runSurface) {
    await expect(page.locator(".run-summary")).toBeVisible();
    await expect(page.locator(".phase-strip")).toBeVisible();
    await expect(
      page.getByRole("tabpanel").locator(".panel").first(),
    ).toBeVisible();
  } else {
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
    await expect(page.locator(".project-card").first()).toBeVisible();
    await expect(page.locator(".overview-stat-grid")).toBeVisible();
    await expect(page.locator("#projects.panel")).toBeVisible();
  }
  const palette = await page.evaluate(() => {
    const style = globalThis.getComputedStyle(
      globalThis.document.documentElement,
    );
    return {
      canvas: style.getPropertyValue("--canvas").trim().toLowerCase(),
      magenta: style.getPropertyValue("--magenta").trim().toLowerCase(),
      violet: style.getPropertyValue("--violet").trim().toLowerCase(),
      electric: style.getPropertyValue("--electric").trim().toLowerCase(),
    };
  });
  expect(palette).toEqual({
    canvas: "#07070f",
    magenta: "#f542a7",
    violet: "#8b5cf6",
    electric: "#4b8cff",
  });
  expect(
    await page.evaluate(
      () =>
        globalThis.document.documentElement.scrollWidth <=
        globalThis.document.documentElement.clientWidth + 1,
    ),
  ).toBeTruthy();
}

async function overview() {
  const response = await page.goto(base + "/", {
    waitUntil: "domcontentloaded",
  });
  if (!response?.ok())
    throw new Error(
      "Workspace page returned HTTP " + (response?.status() ?? "unknown"),
    );
  await page.getByRole("heading", { name: "Projects" }).waitFor();
  await settleLayout();
  await assertPitchSurface(false);
}

async function run(id) {
  const response = await page.goto(base + "/runs/" + id, {
    waitUntil: "domcontentloaded",
  });
  if (!response?.ok())
    throw new Error(
      "Run page returned HTTP " + (response?.status() ?? "unknown"),
    );
  await page.getByRole("tab", { name: "Mission", exact: true }).waitFor();
  await expect(page.getByRole("status")).toContainText("Live");
  await settleLayout();
  await assertPitchSurface();
}

async function view(name) {
  await page.getByRole("tab", { name, exact: true }).click();
  await page.getByRole("tabpanel").scrollIntoViewIfNeeded();
  await settleLayout();
  await assertPitchSurface();
}

async function capture(name, runSurface = true) {
  await settleLayout();
  await assertPitchSurface(runSurface);
  const image = await page.screenshot({
    path: resolve(staging, name + ".jpg"),
    type: "jpeg",
    quality: 78,
    animations: "disabled",
  });
  if (image.length < 10000)
    throw new Error(name + " screenshot is unexpectedly small");
  captured.add(name);
}

async function publish() {
  const backup = resolve(
    temporaryRoot,
    "dashboard-assets-backup-" + randomUUID(),
  );
  const hasOutput = Boolean(await stat(output).catch(() => null));
  if (hasOutput) await rename(output, backup);
  try {
    await rename(staging, output);
  } catch (error) {
    if (hasOutput) {
      try {
        await rename(backup, output);
      } catch (restoreError) {
        throw new AggregateError(
          [error, restoreError],
          "Could not publish screenshots or restore the previous asset directory.",
          { cause: restoreError },
        );
      }
    }
    throw error;
  }
  if (hasOutput)
    await rm(backup, { recursive: true, force: true }).catch((error) =>
      console.warn(
        "Screenshots were published, but the prior asset backup could not be removed:",
        error,
      ),
    );
}

let published = false;
try {
  await overview();
  await capture("workspace-overview", false);
  await run(active);
  await capture("mission-control");
  await run(completed);
  await view("Graph");
  await expect(
    page.getByRole("tabpanel", { name: "Graph" }).locator(".react-flow__node"),
  ).toHaveCount(9);
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
  await expect(page.locator(".memory-card").first()).toBeVisible({
    timeout: 15000,
  });
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
  await settleLayout();

  const missing = screenshotNames.filter((name) => !captured.has(name));
  if (missing.length)
    throw new Error("Missing staged captures: " + missing.join(", "));
  for (const name of screenshotNames) {
    const file = await stat(resolve(staging, name + ".jpg"));
    if (!file.isFile() || file.size < 10000)
      throw new Error(name + " did not produce a valid staged image");
  }
  if (diagnostics.length) throw new Error([...new Set(diagnostics)].join("\n"));

  await publish();
  published = true;
  console.log(
    "Captured, validated, and published nine persisted runtime views.",
  );
} finally {
  try {
    await browser.close();
  } finally {
    if (!published) await rm(staging, { recursive: true, force: true });
  }
}
