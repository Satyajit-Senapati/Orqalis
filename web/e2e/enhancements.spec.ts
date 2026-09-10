import { expect, test } from "@playwright/test";
const active = process.env.ORQALIS_E2E_RUN_ID;
const complete = process.env.ORQALIS_E2E_COMPLETED_RUN_ID;
test.skip(!active || !complete, "Requires persisted browser fixtures");

test("inspectors retain keyboard navigation and mobile task access", async ({
  page,
}) => {
  await page.goto("/runs/" + complete);
  await page.getByRole("tab", { name: "Tasks", exact: true }).click();
  await page.locator(".task-list-row").first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Dependencies");
  await expect(dialog).toContainText("Subsequent tasks");
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(page.locator(".task-list-row").first()).toBeFocused();
  await page.getByRole("tab", { name: "Agents", exact: true }).click();
  await page.locator(".agent-directory .actor-row").last().click();
  await expect(dialog).toContainText("Provider activity");
  await page.keyboard.press("Escape");
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.getByRole("tab", { name: "Mission", exact: true }).click();
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
