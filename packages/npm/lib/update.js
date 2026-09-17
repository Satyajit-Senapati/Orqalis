import { spawn } from "node:child_process";
import { access, readFile, realpath } from "node:fs/promises";
import { platform } from "node:os";
import { posix, win32 } from "node:path";

const PACKAGE = "orqalis";
const REGISTRY = "https://registry.npmjs.org/";
const UPDATE_USAGE = "Usage: orqalis update [--check]\n";

export function installedPrefix(packageRoot, os = platform()) {
  const paths = os === "win32" ? win32 : posix;
  const root = paths.resolve(packageRoot);
  const modules = paths.dirname(root);
  if (
    paths.basename(root).toLowerCase() !== PACKAGE ||
    paths.basename(modules).toLowerCase() !== "node_modules"
  ) {
    throw new Error(
      "Update requires an npm global installation of orqalis; run npm install -g orqalis@latest instead.",
    );
  }
  if (os === "win32") return paths.dirname(modules);
  const lib = paths.dirname(modules);
  if (paths.basename(lib) !== "lib") {
    throw new Error(
      "Update requires an npm global installation of orqalis; run npm install -g orqalis@latest instead.",
    );
  }
  return paths.dirname(lib);
}

export function compareVersions(left, right) {
  const pattern =
    /^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$/;
  const a = pattern.exec(left);
  const b = pattern.exec(right);
  if (!a || !b)
    throw new Error("Cannot compare installed and registry versions.");
  for (let index = 1; index <= 3; index++) {
    const difference = Number(a[index]) - Number(b[index]);
    if (difference !== 0) return Math.sign(difference);
  }
  if (!a[4] && !b[4]) return 0;
  if (!a[4]) return 1;
  if (!b[4]) return -1;
  const aParts = a[4].split(".");
  const bParts = b[4].split(".");
  for (let index = 0; index < Math.max(aParts.length, bParts.length); index++) {
    if (aParts[index] === undefined) return -1;
    if (bParts[index] === undefined) return 1;
    const aNumeric = /^\d+$/.test(aParts[index]);
    const bNumeric = /^\d+$/.test(bParts[index]);
    if (aNumeric && bNumeric) {
      const difference = Number(aParts[index]) - Number(bParts[index]);
      if (difference !== 0) return Math.sign(difference);
    } else if (aNumeric !== bNumeric) {
      return aNumeric ? -1 : 1;
    } else {
      const order =
        aParts[index] < bParts[index]
          ? -1
          : aParts[index] > bParts[index]
            ? 1
            : 0;
      if (order !== 0) return order;
    }
  }
  return 0;
}

export async function locateNpm(
  os = platform(),
  nodeExecutable = process.execPath,
  exists = access,
  canonicalPath = realpath,
) {
  const paths = os === "win32" ? win32 : posix;
  const nodeDirectory = paths.dirname(await canonicalPath(nodeExecutable));
  const candidates = [
    paths.join(nodeDirectory, "node_modules", "npm", "bin", "npm-cli.js"),
    paths.join(
      nodeDirectory,
      "..",
      "lib",
      "node_modules",
      "npm",
      "bin",
      "npm-cli.js",
    ),
  ];
  for (const candidate of candidates) {
    try {
      await exists(candidate);
      const physical = await canonicalPath(candidate);
      const expected = paths.normalize(candidate);
      const actual = paths.normalize(physical);
      if (
        (os === "win32" ? expected.toLowerCase() : expected) !==
        (os === "win32" ? actual.toLowerCase() : actual)
      ) {
        continue; // Do not follow an npm CLI symlink into the invoking project.
      }
      return candidate;
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
  }
  throw new Error(
    "npm CLI was not found beside this Node installation. Run npm install -g orqalis@latest instead.",
  );
}
export function npmInvocation(
  args,
  os = platform(),
  npmPath,
  nodeExecutable = process.execPath,
) {
  if (!npmPath || !(os === "win32" ? win32 : posix).isAbsolute(npmPath)) {
    throw new Error("npm must be invoked from an absolute installed path.");
  }
  if (npmPath.endsWith("npm-cli.js")) {
    return { command: nodeExecutable, args: [npmPath, ...args] };
  }
  if (os === "win32") {
    throw new Error(
      "Windows updates require npm-cli.js; npm.cmd cannot be invoked safely here.",
    );
  }
  return { command: npmPath, args };
}
export function invokeNpm(args, options = {}) {
  const os = options.os || platform();
  const { command, args: commandArgs } = npmInvocation(
    args,
    os,
    options.npmPath,
    options.nodeExecutable || process.execPath,
  );
  const start = options.start || spawn;
  const capture = options.capture || false;
  return new Promise((accept, reject) => {
    const child = start(command, commandArgs, {
      cwd: (os === "win32" ? win32 : posix).dirname(options.npmPath),
      env: options.env,
      stdio: capture ? ["ignore", "pipe", "inherit"] : "inherit",
      windowsHide: true,
    });
    let output = "";
    if (capture) {
      child.stdout.on("data", (chunk) => {
        output += chunk.toString("utf8");
      });
    }
    child.once("error", reject);
    child.once("exit", (status, signal) => {
      accept({ status: status ?? (signal ? 1 : 0), stdout: output });
    });
  });
}

export async function runUpdate(packageRoot, args = [], options = {}) {
  const stdout = options.stdout || process.stdout;
  const stderr = options.stderr || process.stderr;
  if (args.includes("--help") || args.includes("-h")) {
    stdout.write(UPDATE_USAGE);
    stdout.write(
      "Check the public npm release or install it into this Orqalis global prefix.\n",
    );
    return 0;
  }
  if (args.length > 1 || (args.length === 1 && args[0] !== "--check")) {
    stderr.write(UPDATE_USAGE);
    return 2;
  }
  const os = options.os || platform();
  const paths = os === "win32" ? win32 : posix;
  const prefix = installedPrefix(packageRoot, os);
  const shim =
    os === "win32"
      ? paths.join(prefix, "orqalis.cmd")
      : paths.join(prefix, "bin", "orqalis");
  await (options.access || access)(shim);
  const metadata = JSON.parse(
    await (options.readFile || readFile)(
      paths.join(packageRoot, "package.json"),
      "utf8",
    ),
  );
  if (metadata.name !== PACKAGE || typeof metadata.version !== "string") {
    throw new Error("Installed npm package metadata is invalid.");
  }
  const env = Object.fromEntries(
    Object.entries(options.env || process.env).filter(
      ([name]) => name.toLowerCase() !== "npm_config_prefix",
    ),
  );
  env.npm_config_prefix = prefix;
  const npmPath = await (options.locateNpm || locateNpm)(
    os,
    options.nodeExecutable || process.execPath,
    options.access || access,
    options.realpath || realpath,
  );
  const npm = options.invokeNpm || invokeNpm;
  const lookup = await npm(
    ["view", "orqalis@latest", "version", "--json", "--registry=" + REGISTRY],
    { os, env, npmPath, capture: true },
  );
  if (lookup.status !== 0) {
    throw new Error(
      "Could not check the public npm release (npm exit " +
        lookup.status +
        ").",
    );
  }
  let latest;
  try {
    const response = JSON.parse(lookup.stdout.trim());
    latest =
      Array.isArray(response) && response.length === 1 ? response[0] : response;
  } catch {
    throw new Error("npm returned an invalid latest-version response.");
  }
  if (typeof latest !== "string") {
    throw new Error("npm returned an invalid latest-version response.");
  }
  const order = compareVersions(metadata.version, latest);
  stdout.write(
    "Installed: " + metadata.version + " | npm latest: " + latest + "\n",
  );
  if (order >= 0) {
    stdout.write(
      order === 0
        ? "Orqalis is up to date.\n"
        : "Installed version is newer than npm latest; no downgrade was performed.\n",
    );
    return 0;
  }
  if (args[0] === "--check") {
    stdout.write("An update is available. Run orqalis update to install it.\n");
    return 0;
  }
  stderr.write(
    "Before updating, stop active Orqalis UI/MCP processes, reach a safe run checkpoint, and back up project .orqalis/ directories.\n",
  );
  const install = await npm(
    [
      "install",
      "-g",
      "orqalis@" + latest,
      "--registry=" + REGISTRY,
      "--ignore-scripts",
      "--no-audit",
      "--no-fund",
    ],
    { os, env, npmPath, capture: false },
  );
  if (install.status !== 0) {
    throw new Error(
      "npm update failed (exit " +
        install.status +
        "); the installed version was not verified.",
    );
  }
  stdout.write(
    "Package update completed. Run orqalis --version and orqalis doctor in each initialized project; then restart the UI and reconnect MCP clients.\n",
  );
  return 0;
}
