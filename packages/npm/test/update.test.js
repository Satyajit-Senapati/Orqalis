import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { EventEmitter } from "node:events";
import { platform } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
  compareVersions,
  installedPrefix,
  invokeNpm,
  locateNpm,
  npmInvocation,
  runUpdate,
} from "../lib/update.js";

function harness(
  root,
  current = "1.0.0",
  latest = "1.0.1",
  os = root.startsWith("C:\\") ? "win32" : "linux",
) {
  const calls = [];
  const checked = [];
  let output = "";
  let errors = "";
  let installStatus = 0;
  let lookupStatus = 0;
  const options = {
    os,
    env: { NPM_CONFIG_PREFIX: "wrong-prefix", PATH: "fixture-path" },
    stdout: {
      write: (value) => {
        output += value;
      },
    },
    stderr: {
      write: (value) => {
        errors += value;
      },
    },
    access: async (path) => {
      checked.push(path);
    },
    readFile: async () => JSON.stringify({ name: "orqalis", version: current }),
    locateNpm: async () =>
      os === "win32"
        ? "C:\\Node\\node_modules\\npm\\bin\\npm-cli.js"
        : "/usr/local/bin/npm",
    invokeNpm: async (args, settings) => {
      calls.push({ args, settings });
      return args[0] === "view"
        ? { status: lookupStatus, stdout: JSON.stringify([latest]) + "\n" }
        : { status: installStatus, stdout: "" };
    },
  };
  return {
    root,
    options,
    calls,
    checked,
    get output() {
      return output;
    },
    get errors() {
      return errors;
    },
    setInstallStatus(status) {
      installStatus = status;
    },
    setLookupStatus(status) {
      lookupStatus = status;
    },
  };
}

test("global prefix detection accepts npm layouts and rejects a checkout", () => {
  assert.equal(
    installedPrefix("/opt/npm/lib/node_modules/orqalis", "linux"),
    "/opt/npm",
  );
  assert.equal(
    installedPrefix("/Users/u/.npm-global/lib/node_modules/orqalis", "darwin"),
    "/Users/u/.npm-global",
  );
  assert.equal(
    installedPrefix(
      "C:\\Users\\u\\AppData\\Roaming\\npm\\node_modules\\orqalis",
      "win32",
    ),
    "C:\\Users\\u\\AppData\\Roaming\\npm",
  );
  assert.throws(
    () => installedPrefix("/project/packages/npm", "linux"),
    /npm global installation/,
  );
  assert.throws(
    () => installedPrefix("/project/node_modules/orqalis", "linux"),
    /npm global installation/,
  );
});

test("version ordering prevents downgrade and handles prereleases", () => {
  assert.equal(compareVersions("1.0.0", "1.0.1"), -1);
  assert.equal(compareVersions("1.1.0", "1.0.1"), 1);
  assert.equal(compareVersions("1.0.1", "1.0.1"), 0);
  assert.equal(compareVersions("1.0.1-beta.2", "1.0.1-beta.10"), -1);
  assert.equal(compareVersions("1.0.1-beta", "1.0.1"), -1);
  assert.equal(compareVersions("1.0.1", "1.0.1-rc.1"), 1);
  assert.throws(() => compareVersions("broken", "1.0.0"), /Cannot compare/);
});

test("npm command uses absolute CLI argv on Windows and POSIX", () => {
  assert.deepEqual(
    npmInvocation(
      ["view", "orqalis@latest", "version"],
      "win32",
      "C:\\Program Files\\nodejs\\node_modules\\npm\\bin\\npm-cli.js",
      "C:\\Program Files\\nodejs\\node.exe",
    ),
    {
      command: "C:\\Program Files\\nodejs\\node.exe",
      args: [
        "C:\\Program Files\\nodejs\\node_modules\\npm\\bin\\npm-cli.js",
        "view",
        "orqalis@latest",
        "version",
      ],
    },
  );
  assert.deepEqual(
    npmInvocation(
      ["install", "-g", "orqalis@1.0.1"],
      "linux",
      "/usr/local/bin/npm",
    ),
    {
      command: "/usr/local/bin/npm",
      args: ["install", "-g", "orqalis@1.0.1"],
    },
  );
  assert.throws(
    () => npmInvocation(["install"], "win32", "C:\\Node\\npm.cmd"),
    /npm-cli.js/,
  );
});

test("npm lookup is Node-relative and rejects symlink redirection", async () => {
  const checked = [];
  const second = "C:\\lib\\node_modules\\npm\\bin\\npm-cli.js";
  const found = await locateNpm(
    "win32",
    "C:\\Node\\node.exe",
    async (candidate) => {
      checked.push(candidate);
      if (candidate !== second) {
        const error = new Error("missing");
        error.code = "ENOENT";
        throw error;
      }
    },
    async (path) => path,
  );
  assert.equal(found, second);
  assert.deepEqual(checked, [
    "C:\\Node\\node_modules\\npm\\bin\\npm-cli.js",
    second,
  ]);
  await assert.rejects(
    locateNpm(
      "win32",
      "C:\\Node\\node.exe",
      async () => {},
      async (path) =>
        path.endsWith("npm-cli.js")
          ? "S:\\project\\node_modules\\npm\\bin\\npm-cli.js"
          : path,
    ),
    /beside this Node installation/,
  );
  await assert.rejects(
    locateNpm(
      "linux",
      "/missing/node",
      async () => {
        const error = new Error("missing");
        error.code = "ENOENT";
        throw error;
      },
      async (path) => path,
    ),
    /beside this Node installation/,
  );
});
test("installed npm executes from its own directory, not the caller project", async () => {
  const npmPath = await locateNpm();
  const result = await invokeNpm(["--version"], { npmPath, capture: true });
  assert.equal(result.status, 0);
  assert.match(result.stdout.trim(), /^\d+\.\d+\.\d+/);
  assert.equal(
    npmPath.endsWith("npm-cli.js") ||
      (platform() !== "win32" && npmPath.endsWith("npm")),
    true,
  );
});
test("npm child runs with the selected prefix and preserves exit status", async () => {
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  let invocation;
  const result = invokeNpm(["view", "orqalis@latest", "version"], {
    os: "linux",
    env: { npm_config_prefix: "/selected" },
    capture: true,
    npmPath: "/trusted/bin/npm",
    start: (command, args, options) => {
      invocation = { command, args, options };
      return child;
    },
  });
  child.stdout.emit("data", Buffer.from('"1.0.1"\n'));
  child.emit("exit", 7, null);
  assert.deepEqual(await result, { status: 7, stdout: '"1.0.1"\n' });
  assert.equal(invocation.options.env.npm_config_prefix, "/selected");
  assert.equal(invocation.options.cwd, "/trusted/bin");
  assert.notEqual(invocation.options.cwd, process.cwd());
  assert.deepEqual(invocation.options.stdio, ["ignore", "pipe", "inherit"]);
  const failed = invokeNpm(["install"], {
    os: "win32",
    npmPath: "C:\\Node\\node_modules\\npm\\bin\\npm-cli.js",
    start: () => {
      const missing = new EventEmitter();
      queueMicrotask(() => missing.emit("error", new Error("npm unavailable")));
      return missing;
    },
  });
  await assert.rejects(failed, /npm unavailable/);
});

test("update --help works before installed-runtime or npm checks", async () => {
  const h = harness("/source/packages/npm");
  assert.equal(await runUpdate(h.root, ["--help"], h.options), 0);
  assert.match(h.output, /Usage: orqalis update/);
  assert.equal(h.calls.length, 0);
});

test("update --check observes the release without installing", async () => {
  const h = harness("/home/u/prefix/lib/node_modules/orqalis");
  assert.equal(await runUpdate(h.root, ["--check"], h.options), 0);
  assert.match(h.output, /Installed: 1.0.0 \| npm latest: 1.0.1/);
  assert.match(h.output, /update is available/);
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0].args[0], "view");
  assert.equal(h.calls[0].settings.env.npm_config_prefix, "/home/u/prefix");
  assert.equal(h.calls[0].settings.env.NPM_CONFIG_PREFIX, undefined);
  assert.deepEqual(h.checked, ["/home/u/prefix/bin/orqalis"]);
});

test("update installs into the same custom global prefix, with no Python or database calls", async () => {
  const h = harness(
    "C:\\custom prefix\\node_modules\\orqalis",
    "1.0.0",
    "1.0.1",
    "win32",
  );
  assert.equal(await runUpdate(h.root, [], h.options), 0);
  assert.deepEqual(h.checked, ["C:\\custom prefix\\orqalis.cmd"]);
  assert.deepEqual(
    h.calls.map((call) => call.args[0]),
    ["view", "install"],
  );
  assert.equal(h.calls[1].settings.env.npm_config_prefix, "C:\\custom prefix");
  assert.equal(h.calls[1].settings.capture, false);
  assert.deepEqual(h.calls[1].args.slice(0, 3), [
    "install",
    "-g",
    "orqalis@1.0.1",
  ]);
  assert.match(h.errors, /back up project \.orqalis\//);
  assert.match(h.output, /orqalis doctor/);
});

test("same or newer installed version is never reinstalled or downgraded", async () => {
  for (const [current, latest, expected] of [
    ["1.0.1", "1.0.1", /up to date/],
    ["1.0.1", "1.0.0", /no downgrade/],
  ]) {
    const h = harness("/prefix/lib/node_modules/orqalis", current, latest);
    assert.equal(await runUpdate(h.root, [], h.options), 0);
    assert.equal(h.calls.length, 1);
    assert.match(h.output, expected);
  }
});

test("unknown arguments and checkout invocation never call npm", async () => {
  const h = harness("/prefix/lib/node_modules/orqalis");
  assert.equal(await runUpdate(h.root, ["--force"], h.options), 2);
  assert.equal(h.calls.length, 0);
  await assert.rejects(
    runUpdate("/source/packages/npm", [], h.options),
    /npm global installation/,
  );
  assert.equal(h.calls.length, 0);
});

test("registry and install failures do not report completion", async () => {
  const unavailable = harness("/prefix/lib/node_modules/orqalis");
  unavailable.setLookupStatus(42);
  await assert.rejects(
    runUpdate(unavailable.root, [], unavailable.options),
    /npm exit 42/,
  );
  assert.equal(unavailable.calls.length, 1);
  const failed = harness("/prefix/lib/node_modules/orqalis");
  failed.setInstallStatus(13);
  await assert.rejects(
    runUpdate(failed.root, [], failed.options),
    /npm update failed/,
  );
  assert.doesNotMatch(failed.output, /Package update completed/);
});

test("checkout launcher rejects update without bootstrapping Python", () => {
  const launcher = join(import.meta.dirname, "../bin/orqalis.js");
  const result = spawnSync(process.execPath, [launcher, "update"], {
    encoding: "utf8",
    env: { ...process.env, ORQALIS_PYTHON: "nonexistent-python" },
    timeout: 10000,
  });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /npm global installation/);
  assert.doesNotMatch(result.stderr, /Python 3.12/);
});
