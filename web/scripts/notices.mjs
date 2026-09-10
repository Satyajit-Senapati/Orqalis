import { readFile, readdir, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const lock = JSON.parse(
  await readFile(join(root, "package-lock.json"), "utf8"),
);
const notices = [
  "Orqalis frontend: third-party notices",
  "The following packages supply the production frontend and its dependencies.",
  "Each retains its own license; Orqalis's MIT license does not replace these terms.",
];
for (const [path, entry] of Object.entries(lock.packages).sort()) {
  if (!path || entry.dev || entry.devOptional) continue;
  const directory = join(root, path);
  const pkg = JSON.parse(
    await readFile(join(directory, "package.json"), "utf8"),
  );
  notices.push(
    "\n" + "=".repeat(72),
    pkg.name + " " + pkg.version,
    "License: " + pkg.license,
  );
  const files = (await readdir(directory)).filter((name) =>
    /^(licen[sc]e|copying|notice)(\.|$)/i.test(name),
  );
  if (!files.length)
    throw new Error("Missing license text for production package " + pkg.name);
  for (const file of files.sort()) {
    notices.push(
      "\n--- " + file + " ---\n",
      await readFile(join(directory, file), "utf8"),
    );
  }
}
await writeFile(
  join(root, "dist/THIRD_PARTY_NOTICES.txt"),
  notices.join("\n") + "\n",
);
