import { expect, test } from "@playwright/test";
import type { Snapshot } from "../src/types";
const active = process.env.ORQALIS_E2E_RUN_ID;
const complete = process.env.ORQALIS_E2E_COMPLETED_RUN_ID;
test.skip(!active || !complete, "Requires persisted browser fixtures");
const motionSelectors = [
  ".shell",
  ".sidebar",
  ".brand-mark",
  ".run-summary",
  ".progress-track i",
  ".phase-strip",
  ".phase-strip .active-phase > span",
  ".panel",
  ".react-flow__edge-path",
  ".connection .green",
];

async function visualMotion(page: import("@playwright/test").Page) {
  return page.evaluate((selectors) => {
    const styles = selectors.flatMap((selector) => {
      const element = document.querySelector(selector);
      if (!element) return [];
      return [
        getComputedStyle(element),
        getComputedStyle(element, "::before"),
        getComputedStyle(element, "::after"),
      ];
    });
    return styles.map((style) => ({
      animationName: style.animationName,
      animationDuration: style.animationDuration,
      transitionDuration: style.transitionDuration,
    }));
  }, motionSelectors);
}

test("inspectors retain keyboard navigation and mobile task access", async ({
  page,
}) => {
  await page.goto("/runs/" + complete);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const palette = await page.evaluate(() => {
    const style = getComputedStyle(document.documentElement);
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
  const activeMotion = await visualMotion(page);
  expect(
    activeMotion.some(
      (style) =>
        style.animationName !== "none" ||
        [
          ...style.animationDuration.split(","),
          ...style.transitionDuration.split(","),
        ].some((duration) => Number.parseFloat(duration) > 0),
    ),
  ).toBeTruthy();
  await page.getByRole("tab", { name: "Tasks", exact: true }).click();
  await expect(
    page.locator(".task-list-row .badge[class*=status-]").first(),
  ).toBeVisible();
  await page.locator(".task-list-row").first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Dependencies");
  await expect(dialog).toContainText("Subsequent tasks");
  const firstInspectorTitle = await dialog.locator("h2").textContent();
  const subsequentTask = dialog
    .locator('h3:has-text("Subsequent tasks") + p .text-link')
    .first();
  await expect(subsequentTask).toBeVisible();
  await dialog.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });
  await subsequentTask.click();
  await expect(dialog.locator("h2")).not.toHaveText(firstInspectorTitle ?? "");
  await expect
    .poll(() => dialog.evaluate((element) => element.scrollTop))
    .toBe(0);
  await expect(dialog.locator("h2")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(page.locator(".task-list-row").first()).toBeFocused();
  await page.getByRole("tab", { name: "Agents", exact: true }).click();
  await expect(
    page.locator(".agent-directory .badge[class*=status-]").first(),
  ).toBeVisible();
  await page.locator(".agent-directory .actor-row").last().click();
  await expect(dialog).toContainText("Provider activity");
  await page.keyboard.press("Escape");
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.getByRole("tab", { name: "Mission", exact: true }).click();
    if (width === 390)
      await expect(page.locator(".workspace-tabs")).toHaveCSS(
        "position",
        "sticky",
      );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    await page.getByLabel("Inspect task").selectOption({ index: 1 });
    await expect(dialog).toBeVisible();
    expect(
      await dialog.evaluate(
        (el) => el.getBoundingClientRect().right <= innerWidth,
      ),
    ).toBeTruthy();
    await page.keyboard.press("Escape");
  }
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(
    await page.evaluate(
      () => matchMedia("(prefers-reduced-motion: reduce)").matches,
    ),
  ).toBeTruthy();
  const reducedMotion = await visualMotion(page);
  expect(reducedMotion.length).toBeGreaterThan(0);
  for (const style of reducedMotion) {
    expect(["", "none"]).toContain(style.animationName);
    for (const duration of [
      ...style.animationDuration.split(","),
      ...style.transitionDuration.split(","),
    ])
      if (duration.trim()) expect(Number.parseFloat(duration)).toBe(0);
  }
});

test("skills, context, chronological filters and delivery are connected", async ({
  page,
}) => {
  await page.goto("/runs/" + complete);
  await page.getByRole("tab", { name: "Skills", exact: true }).click();
  await expect(page.locator(".skill-card")).toHaveCount(3);
  await expect(
    page.locator(".skill-card").filter({ hasText: "python-edit" }),
  ).toContainText("1.0.0");
  await page.getByRole("tab", { name: "Activity", exact: true }).click();
  const activityPanel = page.getByRole("tabpanel", { name: "Activity" });
  await expect(activityPanel.locator(".activity-row").first()).toBeVisible();
  await page
    .getByLabel("Event type", { exact: true })
    .selectOption("SKILL_LOADED");
  for (const text of await activityPanel
    .locator(".activity-row strong")
    .allTextContents())
    expect(text).toContain("skill loaded");
  await page.getByLabel("Event type", { exact: true }).selectOption("");
  await page.getByLabel("Task", { exact: true }).selectOption({ index: 1 });
  await page.getByRole("tab", { name: "Project Brain", exact: true }).click();
  await expect(page.locator(".memory-card").first()).toBeVisible();
});

test("socket disconnect triggers bounded replay and reconnect without page reload", async ({
  page,
}) => {
  let connections = 0;
  await page.routeWebSocket("**/ws/runs/**", (socket) => {
    connections++;
    const server = socket.connectToServer();
    server.onMessage((message) => {
      socket.send(message);
      if (connections === 1 && String(message).includes('"type":"snapshot"'))
        socket.close();
    });
  });
  await page.goto("/runs/" + active);
  await expect.poll(() => connections, { timeout: 15000 }).toBeGreaterThan(1);
  await expect(page.getByRole("status")).toContainText("Live");
  const ids = await page.locator(".activity-row>small").allTextContents();
  expect(new Set(ids).size).toBe(ids.length);
  expect(
    Number(await page.getByRole("progressbar").getAttribute("aria-valuenow")),
  ).toBeCloseTo(100 / 3, 5);
});

test("empty history and unavailable runs have honest actionable states", async ({
  page,
}) => {
  await page.route("**/api/runs", (route) => route.fulfill({ json: [] }));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "No runs yet" }),
  ).toBeVisible();
  await page.route(
    "**/api/runs/00000000-0000-0000-0000-000000000000",
    (route) => route.fulfill({ status: 404, json: { code: "not_found" } }),
  );
  await page.goto("/runs/00000000-0000-0000-0000-000000000000");
  await expect(
    page.getByRole("heading", { name: "Run unavailable" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Retry connection" }),
  ).toBeVisible();
});

test("run history stays bounded while older runs remain reachable", async ({
  page,
  request,
}) => {
  const existing = await (await request.get("/api/runs")).json();
  const runs = Array.from({ length: 51 }, (_, i) => ({
    ...existing[0],
    id: "history-" + i,
    request: "History fixture " + i,
  }));
  await page.route("**/api/runs", (route) => route.fulfill({ json: runs }));
  await page.goto("/");
  const history = page.locator("#runs");
  await expect(history.locator(".history-row")).toHaveCount(50);
  await expect(
    page.getByRole("button", { name: "Previous runs" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Next runs" }).click();
  await expect(history.locator(".history-row")).toHaveCount(1);
  await expect(history.locator(".history-row")).toHaveAttribute(
    "href",
    "/runs/history-50",
  );
  await expect(page.getByRole("button", { name: "Next runs" })).toBeDisabled();
  await page.getByRole("button", { name: "Previous runs" }).click();
  await expect(history.locator(".history-row")).toHaveCount(50);
});

test("project navigation stays reachable across desktop and mobile", async ({
  page,
  request,
}) => {
  const sourceProjects = (await (
    await request.get("/api/projects")
  ).json()) as Array<{
    id: string;
    name: string;
    repo_root: string;
    default_branch: string;
  }>;
  const sourceRuns = (await (await request.get("/api/runs")).json()) as Array<{
    id: string;
    project_id: string;
    request: string;
    state: string;
    target_branch: string;
    created_at: string;
    repair_iteration: number;
  }>;
  const firstProject = {
    ...sourceProjects[0],
    name: "Orqalis platform and orchestration workspace",
  };
  const secondProject = {
    ...firstProject,
    id: "22222222-2222-4222-8222-222222222222",
    name: "Payments service with a deliberately long project name",
    repo_root: "S:/workspaces/payments-service",
    default_branch: "main",
  };
  const firstRun = {
    ...sourceRuns[0],
    id: "33333333-3333-4333-8333-333333333333",
    project_id: firstProject.id,
    request: "Harden project navigation",
  };
  const secondRun = {
    ...firstRun,
    id: "44444444-4444-4444-8444-444444444444",
    project_id: secondProject.id,
    request: "Verify payment workflow",
  };

  await page.route("**/api/projects", (route) =>
    route.fulfill({ json: [firstProject, secondProject] }),
  );
  await page.route("**/api/runs", (route) =>
    route.fulfill({ json: [firstRun, secondRun] }),
  );

  await page.setViewportSize({ width: 1024, height: 500 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
  await expect(page.locator(".project-card")).toHaveCount(2);
  const primary = page.getByRole("navigation", { name: "Primary" });
  await expect(
    primary.getByRole("link", { name: "Mission Control" }),
  ).toHaveAttribute("href", "/runs/" + firstRun.id);

  const sidebarGeometry = await page.locator(".sidebar").evaluate((sidebar) => {
    const footer = sidebar.querySelector(".sidebar-bottom")!;
    const scroll = sidebar.querySelector(".sidebar-scroll")!;
    const projectLink = sidebar.querySelector(".project-nav a")!;
    return {
      footerBottom: footer.getBoundingClientRect().bottom,
      footerTop: footer.getBoundingClientRect().top,
      overflowY: getComputedStyle(scroll).overflowY,
      projectFits: projectLink.scrollWidth <= projectLink.clientWidth,
    };
  });
  expect(sidebarGeometry.footerTop).toBeGreaterThanOrEqual(0);
  expect(sidebarGeometry.footerBottom).toBeLessThanOrEqual(500);
  expect(sidebarGeometry.overflowY).toBe("auto");
  expect(sidebarGeometry.projectFits).toBeTruthy();

  await page
    .getByRole("navigation", { name: "Projects" })
    .getByRole("link", { name: /Payments service/ })
    .click();
  await expect(page).toHaveURL(new RegExp("project=" + secondProject.id));
  await expect(
    page.getByRole("heading", { name: secondProject.name }),
  ).toBeVisible();
  await expect(page.locator("#runs .history-row")).toHaveCount(1);
  await expect(page.locator("#runs .history-row")).toContainText(
    secondRun.request,
  );
  await expect(
    primary.getByRole("link", { name: "Mission Control" }),
  ).toHaveAttribute("href", "/runs/" + secondRun.id);

  await page.setViewportSize({ width: 390, height: 844 });
  const toggle = page.locator(".sidebar-toggle");
  await expect(toggle).toBeVisible();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator(".sidebar-content")).toBeHidden();
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator(".workspace")).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Projects" }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Recent runs" }),
  ).toBeVisible();
  const mobileTargets = await primary
    .locator("a")
    .evaluateAll((links) =>
      links.map((link) => link.getBoundingClientRect().height),
    );
  expect(mobileTargets.every((height) => height >= 44)).toBeTruthy();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.keyboard.press("Escape");
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(toggle).toBeFocused();
  await toggle.click();
  await page
    .locator(".sidebar-backdrop")
    .click({ position: { x: 360, y: 300 } });
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(toggle).toBeFocused();
});

test("home data failures degrade independently without false empty states", async ({
  page,
  request,
}) => {
  const projects = await (await request.get("/api/projects")).json();
  const runs = await (await request.get("/api/runs")).json();
  await page.route("**/api/projects", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 500));
    await route.fulfill({ json: projects });
  });
  await page.route("**/api/runs", (route) =>
    route.fulfill({ status: 500, json: { message: "Run index unavailable" } }),
  );
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Loading workspace" }),
  ).toBeVisible();
  await expect(page.locator(".project-card").first()).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("Run index unavailable");
  await expect(
    page.getByRole("heading", { name: "No runs yet" }),
  ).toBeVisible();

  await page.unroute("**/api/projects");
  await page.unroute("**/api/runs");
  await page.route("**/api/projects", (route) =>
    route.fulfill({
      status: 500,
      json: { message: "Project index unavailable" },
    }),
  );
  await page.route("**/api/runs", (route) => route.fulfill({ json: runs }));
  await page.reload();
  await expect(page.locator("#runs .history-row").first()).toBeVisible();
  await expect(page.getByRole("alert")).toContainText(
    "Project index unavailable",
  );
});

test("event-history failure keeps Mission Control usable", async ({ page }) => {
  await page.route(`**/api/runs/${complete}/events?*`, (route) =>
    route.fulfill({
      status: 500,
      json: { message: "History store unavailable" },
    }),
  );
  await page.goto("/runs/" + complete);
  await expect(
    page.getByRole("progressbar", { name: "Plan completion" }),
  ).toBeVisible();
  await expect(
    page.getByRole("tab", { name: "Mission", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("alert")).toContainText(
    "Event history unavailable: History store unavailable",
  );
  await expect(page.getByRole("status")).toContainText("Degraded");
});
test("timeline detail follows live snapshots and tiny intervals stay operable", async ({
  page,
  request,
}) => {
  const initial = (await (
    await request.get("/api/runs/" + complete)
  ).json()) as Snapshot;
  const updated = structuredClone(initial);
  const changed = updated.timeline[0];
  changed.duration_ms += 7000;
  changed.ended_at = new Date(
    Date.parse(changed.ended_at) + 7000,
  ).toISOString();
  let serveUpdated = false;
  let connections = 0;
  let closeCurrent: (() => void) | null = null;

  await page.route("**/api/runs/" + complete, (route) =>
    route.fulfill({ json: serveUpdated ? updated : initial }),
  );
  await page.routeWebSocket("**/ws/runs/**", (socket) => {
    connections++;
    closeCurrent = () => socket.close();
    const server = socket.connectToServer();
    server.onMessage((message) => {
      if (serveUpdated && String(message).includes('"type":"snapshot"')) {
        socket.send(JSON.stringify({ type: "snapshot", snapshot: updated }));
      } else {
        socket.send(message);
      }
    });
  });

  await page.goto("/runs/" + complete);
  await page.getByRole("tab", { name: "Timeline", exact: true }).click();
  const panel = page.getByRole("tabpanel", { name: "Timeline" });
  const intervalSelect = panel.getByLabel("Inspect interval");
  await expect(intervalSelect.locator("option")).toHaveCount(
    initial.timeline.length + 1,
  );
  expect(
    await intervalSelect.evaluate(
      (element) => element.getBoundingClientRect().height,
    ),
  ).toBeGreaterThanOrEqual(44);
  await intervalSelect.selectOption({ index: 1 });
  const firstBar = panel.locator(".timeline-bar").first();
  await expect(firstBar).toHaveJSProperty("tagName", "BUTTON");
  await firstBar.focus();
  await page.keyboard.press("Enter");
  await expect(firstBar).toHaveAttribute("aria-pressed", "true");
  await expect(panel.locator(".detail-card")).toContainText(
    initial.timeline[0].duration_ms + " ms",
  );

  serveUpdated = true;
  closeCurrent?.();
  await expect.poll(() => connections, { timeout: 15_000 }).toBeGreaterThan(1);
  await expect(panel.locator(".detail-card")).toContainText(
    changed.duration_ms + " ms",
  );
  closeCurrent?.();
  await page.close();
});
