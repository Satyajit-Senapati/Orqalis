import { expect, test } from "@playwright/test";

const runId = process.env.ORQALIS_E2E_COMPLETED_RUN_ID;
test.skip(
  !runId,
  "Set ORQALIS_E2E_COMPLETED_RUN_ID to the completed execution fixture",
);

test("Operational views reconstruct a delivered run with keyboard and dark-theme support", async ({
  page,
  request,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.emulateMedia({ colorScheme: "light" });
  await page.addInitScript(() =>
    globalThis.localStorage.setItem("orqalis-theme", "light"),
  );
  await page.goto(`/runs/${runId}`);
  await expect(
    page.getByRole("heading", { name: "Normalize names consistently" }),
  ).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByLabel("Color theme")).toHaveCount(0);
  await page.getByRole("tab", { name: "Graph", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Execution graph" }),
  ).toBeVisible();
  await expect(page.locator(".react-flow__node")).toHaveCount(9);
  await page.getByLabel("Inspect task").selectOption({ index: 1 });
  await expect(page.getByRole("dialog")).toContainText(
    "Attempts and ownership",
  );
  await page.getByRole("button", { name: "Close inspector" }).click();
  await page.screenshot({
    path: info.outputPath("graph-dark.jpg"),
    type: "jpeg",
    quality: 65,
  });
  await page.getByRole("tab", { name: "Graph", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("tab", { name: "Timeline", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  const intervals = (await (
    await request.get(`/api/runs/${runId}/timeline`)
  ).json()) as unknown[];
  await expect(page.locator(".timeline-bar")).toHaveCount(intervals.length);
  await page.locator(".timeline-bar").first().click();
  await page.screenshot({
    path: info.outputPath("timeline-dark.jpg"),
    type: "jpeg",
    quality: 65,
  });
  await page.getByRole("tab", { name: "Acceptance", exact: true }).click();
  await page
    .locator(".evidence-criterion")
    .first()
    .locator("summary")
    .first()
    .click();
  await expect(
    page.locator(".evidence-criterion").first().locator(".evidence-record"),
  ).toHaveCount(2);
  await page.locator(".evidence-record").first().locator("summary").click();
  await expect(page.locator(".evidence-record").first()).toContainText("Hash");
  await page.getByRole("tab", { name: "Project Brain", exact: true }).click();
  await expect(page.locator(".brain-health")).toContainText("Indexed commit", {
    timeout: 15_000,
  });
  await expect(page.locator(".memory-card").first()).toBeVisible();
  await page
    .getByRole("button", { name: "Knowledge graph", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Project knowledge graph" }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Delivery", exact: true }).click();
  await expect(page.locator(".delivery-checkpoints .status-pass")).toHaveCount(
    6,
  );
  await page.getByRole("button", { name: "main.py", exact: true }).click();
  await expect(page.locator(".diff-view")).toContainText(
    "+    return value.strip().lower()",
  );
  await page.screenshot({
    path: info.outputPath("delivery-dark.jpg"),
    type: "jpeg",
    quality: 65,
  });
  await page.getByRole("tab", { name: "Metrics", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Runtime statistics" }),
  ).toBeVisible();
  await expect(page.locator(".stat-grid")).toContainText("Not reported");
  await page.getByLabel("Actor", { exact: true }).selectOption({ index: 1 });
  await expect(page.getByRole("tabpanel")).toContainText("main.py");
  await page.getByLabel("Comparison run").selectOption({ index: 1 });
  await expect(
    page.getByRole("table", { name: "Persisted run comparison" }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: info.outputPath("metrics-mobile.jpg"),
    type: "jpeg",
    quality: 65,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByRole("button", { name: "Cancel run" })).toHaveCount(0);
  expect(errors).toEqual([]);
});
