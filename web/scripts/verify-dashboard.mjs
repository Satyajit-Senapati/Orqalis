import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

const args = process.argv.slice(2);
const webRoot = resolve(import.meta.dirname, "..");
const cli = resolve(webRoot, "node_modules", "@playwright", "test", "cli.js");
const listingOnly = args.includes("--list");
const required = ["ORQALIS_E2E_RUN_ID", "ORQALIS_E2E_COMPLETED_RUN_ID"];
const idPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

if (!listingOnly) {
  const missing = required.filter((name) => !process.env[name]);
  if (missing.length) {
    console.error(
      "Dashboard verification requires fixture IDs: " + missing.join(", "),
    );
    console.error(
      "Run tests.e2e.seed_runtime and tests.e2e.seed_execution first.",
    );
    process.exit(2);
  }
  for (const name of required) {
    if (!idPattern.test(process.env[name])) {
      console.error(name + " must contain a persisted run UUID.");
      process.exit(2);
    }
  }
  const base = process.env.ORQALIS_UI_URL || "http://127.0.0.1:7842";
  for (const name of required) {
    const response = await fetch(base + "/api/runs/" + process.env[name], {
      signal: AbortSignal.timeout(10000),
    }).catch((error) => {
      console.error("Cannot reach Orqalis at " + base + ": " + error.message);
      process.exit(2);
    });
    if (!response.ok) {
      console.error(
        name +
          " is unavailable from " +
          base +
          " (HTTP " +
          response.status +
          ").",
      );
      process.exit(2);
    }
  }
}

const result = spawnSync(process.execPath, [cli, "test", ...args], {
  cwd: webRoot,
  env: process.env,
  stdio: "inherit",
});
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
