import { createHash } from "node:crypto";
import { access, readFile, readdir } from "node:fs/promises";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const sha256 = (bytes) =>
  createHash("sha256").update(bytes).digest("hex");

function ignoredSourceArtifact(name) {
  return (
    name === "__pycache__" ||
    name === ".DS_Store" ||
    name === "Thumbs.db" ||
    name.endsWith(".pyc") ||
    name.endsWith(".pyo")
  );
}

async function treeFiles(root, relativeRoot, ignoreArtifacts = false) {
  const output = [];
  async function visit(relativePath) {
    const entries = await readdir(resolve(root, relativePath), {
      withFileTypes: true,
    });
    for (const entry of entries) {
      if (ignoreArtifacts && ignoredSourceArtifact(entry.name)) continue;
      const child = `${relativePath}/${entry.name}`;
      if (entry.isSymbolicLink()) {
        throw new Error(`Release content cannot contain symlinks: ${child}`);
      }
      if (entry.isDirectory()) await visit(child);
      else if (entry.isFile()) output.push(child);
      else throw new Error(`Unsupported release content: ${child}`);
    }
  }
  await visit(relativeRoot);
  return output.sort();
}

async function requireSameFile(source, prepared, area) {
  if (sha256(await readFile(source)) !== sha256(await readFile(prepared))) {
    throw new Error(
      `Prepared ${area} is stale. Run scripts/prepare_npm.py before packing.`,
    );
  }
}

async function requireSameTree(repository, packageRoot, relativeRoot, area) {
  const maintainerDocs = new Set([
    "docs/NPM_RELEASE_READINESS.md",
    "docs/REPOSITORY_CLEANUP_AUDIT.md",
    "docs/verification/npm-release-readiness.json",
  ]);
  const sourceFiles = (await treeFiles(repository, relativeRoot, true)).filter(
    (name) => !maintainerDocs.has(name),
  );
  const preparedFiles = await treeFiles(packageRoot, relativeRoot);
  if (JSON.stringify(sourceFiles) !== JSON.stringify(preparedFiles)) {
    throw new Error(
      `Prepared ${area} inventory is stale. Run scripts/prepare_npm.py before packing.`,
    );
  }
  await Promise.all(
    sourceFiles.map((name) =>
      requireSameFile(
        resolve(repository, name),
        resolve(packageRoot, name),
        area,
      ),
    ),
  );
}

export async function verifyPreparedCheckout(packageRoot, repository) {
  const pkg = JSON.parse(
    await readFile(resolve(packageRoot, "package.json"), "utf8"),
  );
  const manifest = JSON.parse(
    await readFile(resolve(packageRoot, "vendor/manifest.json"), "utf8"),
  );
  for (const name of ["LICENSE", "README.md", "SIGNOFF.md"]) {
    await requireSameFile(
      resolve(repository, name),
      resolve(packageRoot, name),
      name,
    );
  }
  await requireSameTree(repository, packageRoot, "docs", "documentation");
  await requireSameTree(
    repository,
    packageRoot,
    "src/orqalis/skills/bundled",
    "bundled skills",
  );
  const wheel = `orqalis-${pkg.version}-py3-none-any.whl`;
  await requireSameFile(
    resolve(repository, ".tools/release", wheel),
    resolve(packageRoot, "vendor", wheel),
    "release wheel",
  );
  const sourceFiles = await treeFiles(repository, "src/orqalis", true);
  const source = Object.fromEntries(
    await Promise.all(
      sourceFiles.map(async (name) => [
        name.slice("src/orqalis/".length),
        sha256(await readFile(resolve(repository, name))),
      ]),
    ),
  );
  if (
    JSON.stringify(Object.keys(manifest.source ?? {}).sort()) !==
      JSON.stringify(Object.keys(source).sort()) ||
    Object.entries(source).some(
      ([name, hash]) => manifest.source[name] !== hash,
    )
  ) {
    throw new Error(
      "Prepared Python source is stale. Rebuild the wheel and run scripts/prepare_npm.py before packing.",
    );
  }
  const inputs = ["pyproject.toml", "uv.lock", "hatch_build.py"];
  if (
    JSON.stringify(Object.keys(manifest.build_inputs ?? {}).sort()) !==
    JSON.stringify(inputs.sort())
  ) {
    throw new Error(
      "Prepared build inputs are stale. Run scripts/prepare_npm.py before packing.",
    );
  }
  for (const name of inputs) {
    if (
      sha256(await readFile(resolve(repository, name))) !==
      manifest.build_inputs[name]
    ) {
      throw new Error(
        `Prepared build input ${name} is stale. Rebuild the wheel and run scripts/prepare_npm.py before packing.`,
      );
    }
  }
  const webFiles = await treeFiles(repository, "web/dist");
  const web = Object.fromEntries(
    await Promise.all(
      webFiles.map(async (name) => [
        name.slice("web/dist/".length),
        sha256(await readFile(resolve(repository, name))),
      ]),
    ),
  );
  if (
    JSON.stringify(Object.keys(manifest.web ?? {}).sort()) !==
      JSON.stringify(Object.keys(web).sort()) ||
    Object.entries(web).some(([name, hash]) => manifest.web[name] !== hash)
  ) {
    throw new Error(
      "Prepared frontend is stale. Rebuild the UI and run scripts/prepare_npm.py before packing.",
    );
  }
}

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
    "README.md",
    "SIGNOFF.md",
    "docs/PUBLISHING.md",
  ]) {
    if (!(await readFile(resolve(root, name), "utf8")).trim()) {
      throw new Error("Missing release documentation: " + name);
    }
  }
  const repository = resolve(root, "../..");
  if (resolve(repository, "packages/npm") === root) {
    let checkout = true;
    try {
      await access(resolve(repository, "scripts/prepare_npm.py"));
    } catch (error) {
      if (error?.code === "ENOENT") checkout = false;
      else throw error;
    }
    if (checkout) await verifyPreparedCheckout(root, repository);
  }
}
