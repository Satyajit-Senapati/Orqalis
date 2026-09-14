import { spawn, spawnSync } from "node:child_process";
import {
  mkdir,
  readFile,
  writeFile,
  unlink,
  rmdir,
  access,
} from "node:fs/promises";
import { homedir, platform, arch, constants } from "node:os";
import { join, resolve, isAbsolute } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { verifyBundle } from "./bundle.js";

export function cacheRoot(env = process.env, os = platform()) {
  const override = env.ORQALIS_RUNTIME_HOME;
  if (override && !isAbsolute(override))
    throw new Error("ORQALIS_RUNTIME_HOME must be absolute.");
  const configured = os === "win32" ? env.LOCALAPPDATA : env.XDG_CACHE_HOME;
  const base =
    configured && isAbsolute(configured)
      ? configured
      : os === "win32"
        ? join(homedir(), "AppData", "Local")
        : join(homedir(), ".cache");
  return (
    override ||
    (os === "win32"
      ? join(base, "Orqalis", "runtimes")
      : join(base, "orqalis", "runtimes"))
  );
}

export function findPython(
  env = process.env,
  os = platform(),
  probe = spawnSync,
) {
  const candidates = env.ORQALIS_PYTHON
    ? [[env.ORQALIS_PYTHON, []]]
    : os === "win32"
      ? [
          ["py", ["-3"]],
          ["python", []],
          ["python3", []],
        ]
      : [
          ["python3", []],
          ["python", []],
        ];
  for (const [command, prefix] of candidates) {
    const result = probe(
      command,
      [
        ...prefix,
        "-I",
        "-c",
        "import json,sys; print(json.dumps(list(sys.version_info[:2])))",
      ],
      { encoding: "utf8", timeout: 10000, windowsHide: true, env },
    );
    try {
      const [major, minor] = JSON.parse(result.stdout);
      if (result.status === 0 && major === 3 && minor >= 12)
        return { command, prefix };
    } catch {
      /* Try the next interpreter, including Windows Store aliases. */
    }
  }
  throw new Error(
    "Python 3.12+ with venv/pip is required. Install Python, or set ORQALIS_PYTHON to its executable path.",
  );
}

export function runSetup(command, args, options = {}) {
  return new Promise((accept, reject) => {
    // Bootstrap output must never corrupt JSON output or MCP stdio framing.
    const child = spawn(command, args, {
      stdio: ["ignore", 2, 2],
      windowsHide: true,
      timeout: 600000,
      ...options,
    });
    child.once("error", reject);
    child.once("exit", (code, signal) =>
      code === 0
        ? accept()
        : reject(
            new Error(
              `Python setup failed (${signal || code}). Check stderr and retry.`,
            ),
          ),
    );
  });
}

export async function withLock(directory, work, timeout = 660000) {
  const start = Date.now();
  while (true) {
    try {
      await mkdir(directory);
      break;
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      if (Date.now() - start >= timeout) {
        throw new Error(
          `Runtime setup lock timed out: ${directory}. If no setup is running, remove this lock directory and retry.`,
          { cause: error },
        );
      }
      await delay(Math.min(250, timeout));
    }
  }
  try {
    await writeFile(
      join(directory, "owner.json"),
      JSON.stringify({ pid: process.pid, started: new Date().toISOString() }),
    );
    return await work();
  } finally {
    await unlink(join(directory, "owner.json")).catch((error) => {
      if (error.code !== "ENOENT") throw error;
    });
    await rmdir(directory);
  }
}

export async function ensureRuntime(root, options = {}) {
  const env = options.env || process.env;
  const bundle = await verifyBundle(root);
  const base = resolve(cacheRoot(env));
  const runtime = join(
    base,
    `${bundle.version}-${bundle.fingerprint.slice(0, 20)}-${platform()}-${arch()}`,
  );
  const python = join(
    runtime,
    platform() === "win32" ? "Scripts/python.exe" : "bin/python",
  );
  const marker = join(runtime, "ready.json");
  async function ready() {
    try {
      const record = JSON.parse(await readFile(marker, "utf8"));
      await access(python);
      return record.fingerprint === bundle.fingerprint;
    } catch (error) {
      if (error.code === "ENOENT" || error instanceof SyntaxError) return false;
      throw error;
    }
  }
  if (await ready()) return python;
  await mkdir(base, { recursive: true, mode: 0o700 });
  return withLock(runtime + ".lock", async () => {
    if (await ready()) return python;
    const source = (options.findPython || findPython)(env);
    const setup = options.runSetup || runSetup;
    process.stderr.write(
      `Orqalis: preparing isolated Python runtime ${bundle.version} at ${runtime}\n`,
    );
    await setup(
      source.command,
      [...source.prefix, "-I", "-m", "venv", runtime],
      { env },
    );
    const pip = [
      "-I",
      "-m",
      "pip",
      "--isolated",
      "--disable-pip-version-check",
    ];
    await setup(
      python,
      [
        ...pip,
        "install",
        "--require-hashes",
        "--only-binary=:all:",
        "-r",
        join(root, "vendor/requirements.txt"),
      ],
      { env },
    );
    await setup(
      python,
      [
        ...pip,
        "install",
        "--no-deps",
        "--no-index",
        join(root, "vendor", bundle.wheel),
      ],
      { env },
    );
    await setup(python, [...pip, "check"], { env });
    await setup(
      python,
      [
        "-I",
        "-c",
        'import importlib.metadata; assert importlib.metadata.version("orqalis") == "' +
          bundle.version +
          '"',
      ],
      { env },
    );
    await writeFile(
      marker,
      JSON.stringify({ fingerprint: bundle.fingerprint }),
      { mode: 0o600 },
    );
    return python;
  });
}

export function forward(python, args, options = {}, start = spawn) {
  return new Promise((accept, reject) => {
    const child = start(python, ["-I", "-m", "orqalis", ...args], {
      stdio: "inherit",
      windowsHide: true,
      ...options,
    });
    const handlers = new Map(
      ["SIGINT", "SIGTERM"].map((signal) => {
        const handler = () => {
          if (!child.killed) child.kill(signal);
        };
        process.on(signal, handler);
        return [signal, handler];
      }),
    );
    const cleanup = () => {
      for (const [signal, handler] of handlers) process.off(signal, handler);
    };
    child.once("error", (error) => {
      cleanup();
      reject(error);
    });
    child.once("exit", (code, signal) => {
      cleanup();
      accept(code ?? 128 + (constants.signals[signal] ?? 1));
    });
  });
}
