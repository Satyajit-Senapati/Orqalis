import { expect, test } from "@playwright/test";
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
  await expect(page.locator(".activity-row").first()).toBeVisible();
  await page
    .getByLabel("Event type", { exact: true })
    .selectOption("SKILL_LOADED");
  for (const text of await page
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
  await expect(page.locator(".history-row")).toHaveCount(50);
  await expect(
    page.getByRole("button", { name: "Previous runs" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Next runs" }).click();
  await expect(page.locator(".history-row")).toHaveCount(1);
  await expect(page.locator(".history-row")).toHaveAttribute(
    "href",
    "/runs/history-50",
  );
  await expect(page.getByRole("button", { name: "Next runs" })).toBeDisabled();
  await page.getByRole("button", { name: "Previous runs" }).click();
  await expect(page.locator(".history-row")).toHaveCount(50);
});
