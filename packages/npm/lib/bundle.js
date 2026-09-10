import { createHash } from "node:crypto";
import { readFile, readdir } from "node:fs/promises";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const sha256 = (bytes) =>
  createHash("sha256").update(bytes).digest("hex");

export async function verifyBundle(root) {
  const pkg = JSON.parse(await readFile(resolve(root, "package.json"), "utf8"));
  const raw = await readFile(resolve(root, "vendor/manifest.json"));
  const manifest = JSON.parse(raw);
  if (
    manifest.version !== pkg.version ||
    manifest.schema !== 1 ||
    manifest.license !== pkg.license ||
    !/^\d+\.\d+\.\d+$/.test(pkg.version)
  ) {
    throw new Error(
      "Bundle metadata does not match the npm release. Run scripts/prepare_npm.py.",
    );
  }
  const expected = [
    `orqalis-${pkg.version}-py3-none-any.whl`,
    "requirements.txt",
  ];
  if (
    Object.keys(manifest.files ?? {})
      .sort()
      .join(",") !== expected.sort().join(",")
  ) {
    throw new Error(
      "Bundle must contain exactly the release wheel and locked requirements.",
    );
  }
  if (
    (await readdir(resolve(root, "vendor"))).sort().join(",") !==
    [...expected, "manifest.json"].sort().join(",")
  ) {
    throw new Error(
      "Unexpected files in vendor/. Remove stale build artifacts before packing.",
    );
  }
  for (const [name, hash] of Object.entries(manifest.files)) {
    if (
      basename(name) !== name ||
      !/^[a-f0-9]{64}$/.test(hash) ||
      sha256(await readFile(resolve(root, "vendor", name))) !== hash
    ) {
      throw new Error(`Bundle integrity check failed: ${name}`);
    }
  }
  return {
    version: pkg.version,
    fingerprint: sha256(raw),
    wheel: expected.find((n) => n.endsWith(".whl")),
  };
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  await verifyBundle(root);
  for (const name of [
    "LICENSE",
    "GUIDE.md",
    "README.md",
    "docs/PUBLISHING.md",
  ]) {
    if (!(await readFile(resolve(root, name), "utf8")).trim()) {
      throw new Error("Missing release documentation: " + name);
    }
  }
}
