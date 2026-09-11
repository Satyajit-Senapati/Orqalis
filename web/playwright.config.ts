import { defineConfig } from "@playwright/test";

export default defineConfig({
  workers: Number(process.env.ORQALIS_E2E_WORKERS ?? 1),
  testDir: "./e2e",
  outputDir: "../.tools/browser-results",
  use: {
    baseURL: process.env.ORQALIS_UI_URL || "http://127.0.0.1:7842",
    browserName: "chromium",
    channel:
      process.env.ORQALIS_BROWSER_CHANNEL === "chromium"
        ? undefined
        : process.env.ORQALIS_BROWSER_CHANNEL || "chrome",
    headless: true,
    viewport: { width: 1440, height: 1100 },
  },
});
