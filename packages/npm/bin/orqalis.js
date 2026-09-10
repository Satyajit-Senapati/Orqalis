#!/usr/bin/env node
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { ensureRuntime, forward } from "../lib/runtime.js";

try {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  const python = await ensureRuntime(root);
  process.exitCode = await forward(python, process.argv.slice(2));
} catch (error) {
  process.stderr.write(`orqalis launcher: ${error.message}\n`);
  process.exitCode = 1;
}
