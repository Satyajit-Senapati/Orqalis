import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { EventEmitter } from "node:events";
import {
  mkdtemp,
  mkdir,
  writeFile,
  readFile,
  access,
  readdir,
  rm,
} from "node:fs/promises";
import { tmpdir, platform } from "node:os";
import { join, resolve, sep } from "node:path";
import test from "node:test";
import { sha256, verifyBundle, verifyPreparedCheckout } from "../lib/bundle.js";
import {
  cacheRoot,
  findPython,
  ensureRuntime,
  withLock,
  forward,
} from "../lib/runtime.js";

async function fixture(t) {
  const root = await mkdtemp(join(tmpdir(), "orqalis-launcher-test-"));
  t.after(async () => {
    // Only remove the unique test directory created by mkdtemp.
    assert.ok(resolve(root).startsWith(resolve(tmpdir()) + sep));
    await rm(root, { recursive: true, force: true });
  });
  await mkdir(join(root, "vendor"));
  await writeFile(
    join(root, "package.json"),
    JSON.stringify({ version: "1.0.0", license: "MIT" }),
  );
  const files = {
    "orqalis-1.0.0-py3-none-any.whl": "wheel fixture",
    "requirements.txt": "locked fixture",
  };
  for (const [name, content] of Object.entries(files))
    await writeFile(join(root, "vendor", name), content);
  await writeFile(
    join(root, "vendor/manifest.json"),
    JSON.stringify({
      schema: 1,
      version: "1.0.0",
      license: "MIT",
      files: Object.fromEntries(
        Object.entries(files).map(([name, content]) => [name, sha256(content)]),
      ),
    }),
  );
  return root;
}

async function preparedCheckout(t) {
  const repository = await mkdtemp(join(tmpdir(), "orqalis-checkout-test-"));
  t.after(async () => {
    assert.ok(resolve(repository).startsWith(resolve(tmpdir()) + sep));
    await rm(repository, { recursive: true, force: true });
  });
  const packageRoot = join(repository, "packages/npm");
  for (const directory of [
    "docs",
    "src/orqalis/skills/bundled/example",
    "web/dist",
    ".tools/release",
    "packages/npm/docs",
    "packages/npm/src/orqalis/skills/bundled/example",
    "packages/npm/vendor",
  ]) {
    await mkdir(join(repository, directory), { recursive: true });
  }
  const direct = {
    LICENSE: "MIT fixture",
    "README.md": "README fixture",
    "SIGNOFF.md": "Sign-off fixture",
  };
  for (const [name, content] of Object.entries(direct)) {
    await writeFile(join(repository, name), content);
    await writeFile(join(packageRoot, name), content);
  }
  const trees = {
    "docs/guide.md": "Guide fixture",
    "src/orqalis/skills/bundled/example/skill.toml": "id = example",
  };
  for (const [name, content] of Object.entries(trees)) {
    await writeFile(join(repository, name), content);
    await writeFile(join(packageRoot, name), content);
  }
  await writeFile(
    join(packageRoot, "package.json"),
    JSON.stringify({ version: "1.0.0", license: "MIT" }),
  );
  await writeFile(join(repository, "src/orqalis/__init__.py"), "version = 1");
  const buildInputs = {
    "pyproject.toml": "project fixture",
    "uv.lock": "dependency lock fixture",
    "hatch_build.py": "build hook fixture",
  };
  for (const [name, content] of Object.entries(buildInputs)) {
    await writeFile(join(repository, name), content);
  }
  const wheelName = "orqalis-1.0.0-py3-none-any.whl";
  const wheel = "wheel fixture";
  const requirements = "locked fixture";
  const frontend = "<html>fixture</html>";
  await writeFile(join(repository, ".tools/release", wheelName), wheel);
  await writeFile(join(packageRoot, "vendor", wheelName), wheel);
  await writeFile(join(packageRoot, "vendor/requirements.txt"), requirements);
  await writeFile(join(repository, "web/dist/index.html"), frontend);
  await writeFile(
    join(packageRoot, "vendor/manifest.json"),
    JSON.stringify({
      schema: 1,
      version: "1.0.0",
      license: "MIT",
      files: {
        [wheelName]: sha256(wheel),
        "requirements.txt": sha256(requirements),
      },
      web: { "index.html": sha256(frontend) },
      source: {
        "__init__.py": sha256("version = 1"),
        "skills/bundled/example/skill.toml": sha256("id = example"),
      },
      build_inputs: Object.fromEntries(
        Object.entries(buildInputs).map(([name, content]) => [
          name,
          sha256(content),
        ]),
      ),
    }),
  );
  return { packageRoot, repository };
}

test("bundle validates hashes, rejects tampering and extra packed files", async (t) => {
  const root = await fixture(t);
  assert.equal((await verifyBundle(root)).version, "1.0.0");
  await writeFile(join(root, "vendor/requirements.txt"), "tampered");
  await assert.rejects(verifyBundle(root), /integrity/);
  await writeFile(join(root, "vendor/requirements.txt"), "locked fixture");
  await writeFile(join(root, "vendor/old.whl"), "stale");
  await assert.rejects(verifyBundle(root), /Unexpected files/);
});

test("bundle rejects mismatched versions and path traversal", async (t) => {
  const root = await fixture(t);
  const path = join(root, "vendor/manifest.json");
  const manifest = JSON.parse(await readFile(path, "utf8"));
  await writeFile(path, JSON.stringify({ ...manifest, version: "2.0.0" }));
  await assert.rejects(verifyBundle(root), /metadata/);
  await writeFile(
    path,
    JSON.stringify({ ...manifest, files: { "../outside": sha256("") } }),
  );
  await assert.rejects(verifyBundle(root), /exactly/);
});

test("checkout prepack rejects stale generated release content", async (t) => {
  const { packageRoot, repository } = await preparedCheckout(t);
  await verifyPreparedCheckout(packageRoot, repository);

  await writeFile(join(repository, "README.md"), "changed");
  await assert.rejects(
    verifyPreparedCheckout(packageRoot, repository),
    /README\.md is stale/,
  );
  await writeFile(join(repository, "README.md"), "README fixture");

  const extraDoc = join(packageRoot, "docs/extra.md");
  await writeFile(extraDoc, "stale");
  await assert.rejects(
    verifyPreparedCheckout(packageRoot, repository),
    /documentation inventory is stale/,
  );
  await rm(extraDoc);

  const extraSkill = join(
    packageRoot,
    "src/orqalis/skills/bundled/example/stale.md",
  );
  await writeFile(extraSkill, "stale");
  await assert.rejects(
    verifyPreparedCheckout(packageRoot, repository),
    /bundled skills inventory is stale/,
  );
  await rm(extraSkill);

  await writeFile(join(repository, "web/dist/index.html"), "changed");
  await assert.rejects(
    verifyPreparedCheckout(packageRoot, repository),
    /frontend is stale/,
  );
  await writeFile(
    join(repository, "web/dist/index.html"),
    "<html>fixture</html>",
  );

  await writeFile(
    join(repository, ".tools/release/orqalis-1.0.0-py3-none-any.whl"),
    "changed",
  );
  await assert.rejects(
    verifyPreparedCheckout(packageRoot, repository),
    /release wheel is stale/,
  );
});

test("maintainer release audit is excluded while accidental prepared copies fail", async (t) => {
  const { packageRoot, repository } = await preparedCheckout(t);
  await mkdir(join(repository, "docs/verification"));
  for (const name of [
    "docs/NPM_RELEASE_READINESS.md",
    "docs/REPOSITORY_CLEANUP_AUDIT.md",
    "docs/verification/npm-release-readiness.json",
  ]) {
    await writeFile(join(repository, name), "local audit evidence");
  }
  await verifyPreparedCheckout(packageRoot, repository);
  await writeFile(
    join(packageRoot, "docs/NPM_RELEASE_READINESS.md"),
    "accidental audit copy",
  );
  await assert.rejects(
    verifyPreparedCheckout(packageRoot, repository),
    /documentation inventory is stale/,
  );
});

test("checkout prepack rejects source and dependency changes after preparation", async (t) => {
  const { packageRoot, repository } = await preparedCheckout(t);
  await verifyPreparedCheckout(packageRoot, repository);
  const source = join(repository, "src/orqalis/new_module.py");
  await writeFile(source, "changed = True");
  await assert.rejects(
    verifyPreparedCheckout(packageRoot, repository),
    /Python source is stale/,
  );
  await rm(source);
  const existing = join(repository, "src/orqalis/__init__.py");
  await writeFile(existing, "version = 2");
  await assert.rejects(
    verifyPreparedCheckout(packageRoot, repository),
    /Python source is stale/,
  );
  await rm(existing);
  await assert.rejects(
    verifyPreparedCheckout(packageRoot, repository),
    /Python source is stale/,
  );
  await writeFile(existing, "version = 1");
  for (const [name, original] of [
    ["uv.lock", "dependency lock fixture"],
    ["pyproject.toml", "project fixture"],
    ["hatch_build.py", "build hook fixture"],
  ]) {
    await writeFile(join(repository, name), "changed");
    await assert.rejects(
      verifyPreparedCheckout(packageRoot, repository),
      /build input .* is stale/,
    );
    await writeFile(join(repository, name), original);
  }
  await verifyPreparedCheckout(packageRoot, repository);
});

test("Python discovery requires supported Python and honors explicit override", () => {
  const calls = [];
  const probe = (command, args) => {
    calls.push([command, args]);
    return {
      status: 0,
      stdout: JSON.stringify(command === "python3" ? [3, 12] : [3, 11]),
    };
  };
  assert.equal(findPython({}, "linux", probe).command, "python3");
  assert.deepEqual(calls[0][1].slice(0, 2), ["-I", "-c"]);
  assert.throws(
    () => findPython({ ORQALIS_PYTHON: "old-python" }, "linux", probe),
    /3.12/,
  );
  assert.equal(calls.at(-1)[0], "old-python");
  assert.throws(
    () => findPython({}, "win32", () => ({ status: 1, stdout: "not Python" })),
    /3.12/,
  );
});

test("cache override must be absolute", () => {
  assert.throws(
    () => cacheRoot({ ORQALIS_RUNTIME_HOME: "./relative" }),
    /absolute/,
  );
  assert.equal(cacheRoot({ ORQALIS_RUNTIME_HOME: tmpdir() }), tmpdir());
});

test("relative system cache variables cannot select the invoking project", () => {
  for (const os of ["linux", "darwin", "win32"]) {
    const key = os === "win32" ? "LOCALAPPDATA" : "XDG_CACHE_HOME";
    assert.equal(cacheRoot({ [key]: "relative-cache" }, os), cacheRoot({}, os));
    assert.equal(
      cacheRoot({ [key]: tmpdir() }, os),
      join(tmpdir(), os === "win32" ? "Orqalis" : "orqalis", "runtimes"),
    );
  }
});

test("setup lock serializes callers and releases after failure", async (t) => {
  const root = await fixture(t);
  const lock = join(root, "setup.lock");
  const events = [];
  await Promise.all([
    withLock(lock, async () => {
      events.push("a");
      await new Promise((r) => setTimeout(r, 30));
      events.push("b");
    }),
    withLock(lock, async () => {
      events.push("c");
    }),
  ]);
  assert.ok(["a,b,c", "c,a,b"].includes(events.join(",")));
  await assert.rejects(
    withLock(lock, async () => {
      throw new Error("failure");
    }),
    /failure/,
  );
  await assert.rejects(access(lock), { code: "ENOENT" });
  await mkdir(lock);
  await assert.rejects(
    withLock(lock, async () => {}, 10),
    /lock timed out/,
  );
});

test("runtime setup uses isolated hashed installs once across concurrent launches", async (t) => {
  const root = await fixture(t);
  const calls = [];
  const options = {
    env: { ORQALIS_RUNTIME_HOME: join(root, "cache") },
    findPython: () => ({ command: "fixture-python", prefix: [] }),
    runSetup: async (command, args) => {
      calls.push([command, args]);
      if (args.includes("venv")) {
        const runtime = args.at(-1);
        const bin = join(runtime, platform() === "win32" ? "Scripts" : "bin");
        await mkdir(bin, { recursive: true });
        await writeFile(
          join(bin, platform() === "win32" ? "python.exe" : "python"),
          "",
        );
      }
    },
  };
  const [first, second] = await Promise.all([
    ensureRuntime(root, options),
    ensureRuntime(root, options),
  ]);
  assert.equal(first, second);
  assert.equal(calls.length, 5);
  assert.ok(calls[1][1].includes("--require-hashes"));
  assert.ok(calls[1][1].includes("--only-binary=:all:"));
  assert.ok(calls[2][1].includes("--no-deps"));
  assert.ok(calls[2][1].includes("--no-index"));
  assert.equal(await ensureRuntime(root, options), first);
  assert.equal(calls.length, 5);
});

test("failed setup does not mark runtime ready and can retry", async (t) => {
  const root = await fixture(t);
  const cache = join(root, "cache");
  let attempts = 0;
  const options = {
    env: { ORQALIS_RUNTIME_HOME: cache },
    findPython: () => ({ command: "fixture-python", prefix: [] }),
    runSetup: async () => {
      attempts++;
      throw new Error("offline");
    },
  };
  await assert.rejects(ensureRuntime(root, options), /offline/);
  await assert.rejects(ensureRuntime(root, options), /offline/);
  assert.equal(attempts, 2);
  assert.deepEqual(await readdir(cache), []);
});

test("command forwarding preserves arguments, stdio, exit status and signals", async () => {
  const child = new EventEmitter();
  child.killed = false;
  child.kill = (signal) => {
    child.killed = true;
    child.emit("exit", null, signal);
  };
  let invocation;
  const start = (command, args, options) => {
    invocation = { command, args, options };
    return child;
  };
  const count = process.listenerCount("SIGTERM");
  const result = forward(
    "/python path",
    ["run", 'quotes " and $ text', "--repo", "."],
    {},
    start,
  );
  assert.equal(invocation.command, "/python path");
  assert.deepEqual(invocation.args, [
    "-I",
    "-m",
    "orqalis",
    "run",
    'quotes " and $ text',
    "--repo",
    ".",
  ]);
  assert.equal(invocation.options.stdio, "inherit");
  assert.equal(invocation.options.shell, undefined);
  process.emit("SIGTERM");
  assert.equal(await result, 143);
  assert.equal(process.listenerCount("SIGTERM"), count);
  const failed = forward("python", [], {}, start);
  child.emit("exit", 7, null);
  assert.equal(await failed, 7);
});

test("spawn failure removes forwarding signal handlers", async () => {
  const child = new EventEmitter();
  const count = process.listenerCount("SIGINT");
  const result = forward("missing", [], {}, () => child);
  child.emit("error", new Error("ENOENT"));
  await assert.rejects(result, /ENOENT/);
  assert.equal(process.listenerCount("SIGINT"), count);
});

test("real setup subprocess output is confined to stderr", () => {
  const runtimeUrl = new URL("../lib/runtime.js", import.meta.url).href;
  const program = [
    "import { runSetup } from " + JSON.stringify(runtimeUrl) + ";",
    "await runSetup(process.execPath, ['-e', 'console.log(123); console.error(456)']);",
  ].join("\n");
  const result = spawnSync(
    process.execPath,
    ["--input-type=module", "-e", program],
    {
      encoding: "utf8",
      timeout: 10000,
      windowsHide: true,
    },
  );
  assert.equal(result.status, 0);
  assert.equal(result.stdout, "");
  assert.match(result.stderr, /123/);
  assert.match(result.stderr, /456/);
});

test("abnormal child termination retains the signal exit code", async () => {
  const child = new EventEmitter();
  const result = forward("python", [], {}, () => child);
  child.emit("exit", null, "SIGKILL");
  assert.equal(await result, 137);
});

test("prepack requires release documentation for installs without a checkout", async (t) => {
  const root = await fixture(t);
  await mkdir(join(root, "lib"));
  await mkdir(join(root, "docs"));
  await writeFile(
    join(root, "lib/bundle.js"),
    await readFile(new URL("../lib/bundle.js", import.meta.url)),
  );
  await writeFile(
    join(root, "package.json"),
    JSON.stringify({ version: "1.0.0", license: "MIT", type: "module" }),
  );
  for (const name of [
    "LICENSE",
    "README.md",
    "SIGNOFF.md",
    "docs/PUBLISHING.md",
  ]) {
    await writeFile(join(root, name), "fixture content");
  }
  const command = [join(root, "lib/bundle.js")];
  assert.equal(
    spawnSync(process.execPath, command, { encoding: "utf8" }).status,
    0,
  );
  await rm(join(root, "SIGNOFF.md"));
  const missing = spawnSync(process.execPath, command, { encoding: "utf8" });
  assert.notEqual(missing.status, 0);
  assert.match(missing.stderr, /SIGNOFF.md/);
});
