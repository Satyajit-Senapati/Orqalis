#!/usr/bin/env node
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { ensureRuntime, forward } from "../lib/runtime.js";
import { runUpdate } from "../lib/update.js";

try {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  const args = process.argv.slice(2);
  if (args[0] === "update") {
    process.exitCode = await runUpdate(root, args.slice(1));
  } else {
    const python = await ensureRuntime(root);
    process.exitCode = await forward(python, args);
  }
} catch (error) {
  process.stderr.write(`orqalis launcher: ${error.message}\n`);
  process.exitCode = 1;
}
