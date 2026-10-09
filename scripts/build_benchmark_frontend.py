"""Build a revision's frontend in an isolated copy and bind inputs to artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
EXCLUDED = {
    "node_modules",
    "dist",
    ".git",
    ".vite",
    ".vite-temp",
    ".cache",
    ".tmp",
    "coverage",
    "playwright-report",
    "test-results",
}
PIPELINE = "tsc -b && vite build && node scripts/notices.mjs"
INITIAL_BUILDER_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def fingerprint(
    root: Path, *, dependencies: bool = False, artifact: bool = False
) -> dict[str, Any]:
    """Inventory actual inputs, omitting only explicit generated/cache directories."""
    paths: list[str] = []
    excluded = (
        set() if artifact else (EXCLUDED - {"node_modules", "dist"} if dependencies else EXCLUDED)
    )
    for directory, folders, files in os.walk(root, followlinks=False):
        local_excluded = excluded if Path(directory) == root else set()
        folders[:] = sorted(name for name in folders if name not in local_excluded)
        for name in folders:
            path = Path(directory) / name
            if path.is_symlink() or path.is_junction():
                raise ValueError(f"Unbound linked input: {path}")
        for name in sorted(files):
            path = Path(directory) / name
            if not artifact and path.suffix == ".tsbuildinfo":
                continue
            if path.is_symlink():
                raise ValueError(f"Unbound linked input: {path}")
            paths.append(path.relative_to(root).as_posix())
    if not paths:
        raise ValueError(f"Empty input inventory: {root}")
    digest = hashlib.sha256()
    for relative in sorted(paths):
        digest.update(relative.encode() + b"\0" + (root / relative).read_bytes() + b"\0")
    return {"files": sorted(paths), "sha256": digest.hexdigest()}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tools_fingerprint(node: Path) -> dict[str, str]:
    return {
        "node_path": str(node),
        "node_sha256": file_hash(node),
        "node_version": subprocess.run(
            [str(node), "--version"], check=True, capture_output=True, text=True
        ).stdout.strip(),
    }


def validate_build(source: Path, frontend: Path, evidence: Path) -> dict[str, Any]:
    record: dict[str, Any] = json.loads(evidence.read_text(encoding="utf-8"))
    if record.get("schema_version") != 1 or record.get("method") != "isolated-copy-v1":
        raise ValueError("Unsupported frontend build evidence")
    if record.get("status") != "PASS" or record.get("pipeline") != PIPELINE:
        raise ValueError("Frontend build is not qualified")
    if record["source_web"] != fingerprint(source / "web"):
        raise ValueError("Frontend build belongs to different source/web inputs")
    if record["artifact"] != fingerprint(frontend, artifact=True):
        raise ValueError("Frontend artifact does not match its build evidence")
    if record["builder_sha256"] != file_hash(Path(__file__)):
        raise ValueError("Frontend builder changed after artifact qualification")
    dependency_root = Path(record["dependency_root"])
    if record["dependency_lock_sha256"] != file_hash(dependency_root / "package-lock.json"):
        raise ValueError("Frontend dependency lock changed")
    if record["dependency_lock_sha256"] != file_hash(source / "web/package-lock.json"):
        raise ValueError("Frontend dependencies differ from selected source lock")
    if record["dependencies"] != fingerprint(dependency_root / "node_modules", dependencies=True):
        raise ValueError("Frontend dependency inputs changed after build")
    if record["tools"] != tools_fingerprint(Path(record["tools"]["node_path"])):
        raise ValueError("Frontend build tool changed")
    if not (frontend / "index.html").is_file():
        raise ValueError("Frontend artifact has no index.html")
    return record


def build(source: Path, output: Path, dependency_root: Path) -> dict[str, Any]:
    source, output, dependency_root = source.resolve(), output.resolve(), dependency_root.resolve()
    if output.exists() or output.is_relative_to(source / "web"):
        raise ValueError("Build output must be a new directory outside selected source/web")
    if source != REPO and output.is_relative_to(source):
        raise ValueError("Cannot write build artifacts into the selected baseline archive")
    web = source / "web"
    if file_hash(web / "package-lock.json") != file_hash(dependency_root / "package-lock.json"):
        raise ValueError("Reused dependencies require an identical source lockfile")
    if json.loads((web / "package.json").read_text())["scripts"]["build"] != PIPELINE:
        raise ValueError("Unsupported build pipeline; qualify its steps before measuring")
    executable = shutil.which("node")
    if executable is None:
        raise RuntimeError("node executable unavailable")
    node = Path(executable).resolve()
    before = fingerprint(web)
    dependencies = fingerprint(dependency_root / "node_modules", dependencies=True)
    tools = tools_fingerprint(node)
    builder_hash = INITIAL_BUILDER_HASH
    if builder_hash != file_hash(Path(__file__)):
        raise RuntimeError("Frontend builder changed after loading")
    lock_hash = file_hash(dependency_root / "package-lock.json")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    logs: list[str] = []
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="orqalis-qualified-web-") as directory:
        workspace = Path(directory)
        copied = workspace / "web"
        copied.mkdir()
        for relative in before["files"]:
            target = copied / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(web / relative, target)
        # Tailwind honors this Git boundary; dependencies must not become source candidates.
        subprocess.run(
            ["git", "init", str(workspace)],
            check=True,
            capture_output=True,
            creationflags=creationflags,
        )
        (workspace / ".gitignore").write_text("web/node_modules/\nweb/dist/\n*.tsbuildinfo\n")
        link = copied / "node_modules"
        try:
            if os.name == "nt":
                helper = workspace / "link.ps1"
                helper.write_text(
                    "param([string]$LinkPath,[string]$DependencyPath)\n"
                    "New-Item -ItemType Junction -Path $LinkPath "
                    "-Target $DependencyPath -ErrorAction Stop | Out-Null\n"
                )
                subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-File",
                        str(helper),
                        str(link),
                        str(dependency_root / "node_modules"),
                    ],
                    check=True,
                    capture_output=True,
                    creationflags=creationflags,
                )
            else:
                link.symlink_to(dependency_root / "node_modules", target_is_directory=True)
            commands = [
                [str(node), str(link / "typescript/bin/tsc"), "-b"],
                [str(node), str(link / "vite/bin/vite.js"), "build"],
                [str(node), str(copied / "scripts/notices.mjs")],
            ]
            env = {
                key: value
                for key, value in os.environ.items()
                if not key.upper().startswith(("NODE_", "VITE_", "GIT_"))
            }
            for command in commands:
                result = subprocess.run(
                    command,
                    cwd=copied,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=180,
                    creationflags=creationflags,
                )
                logs.append(result.stdout + result.stderr)
                if result.returncode:
                    raise RuntimeError("Isolated frontend build failed: " + logs[-1])
            shutil.copytree(copied / "dist", output / "dist")
        finally:
            # Remove only the checked link, never recursively traverse shared dependencies.
            if not link.absolute().is_relative_to(workspace.resolve()):
                raise RuntimeError("Unexpected dependency link path")
            if link.is_junction():
                link.rmdir()
            elif link.is_symlink():
                link.unlink()
    stable = (
        before == fingerprint(web)
        and dependencies == fingerprint(dependency_root / "node_modules", dependencies=True)
        and tools == tools_fingerprint(node)
        and builder_hash == file_hash(Path(__file__))
        and lock_hash == file_hash(dependency_root / "package-lock.json")
    )
    record = {
        "schema_version": 1,
        "method": "isolated-copy-v1",
        "pipeline": PIPELINE,
        "source_root": str(source),
        "source_web": before,
        "dependency_root": str(dependency_root),
        "dependencies": dependencies,
        "dependency_lock_sha256": lock_hash,
        "tools": tools,
        "builder_sha256": builder_hash,
        "artifact": fingerprint(output / "dist", artifact=True),
        "git_ignore_boundary": ["web/node_modules/", "web/dist/", "*.tsbuildinfo"],
        "status": "PASS" if stable else "FAIL",
    }
    (output / "build.log").write_text("\n".join(logs), encoding="utf-8")
    (output / "build.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    if not stable:
        raise RuntimeError("Frontend build inputs changed during qualification")
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dependencies-root", type=Path, default=REPO / "web")
    args = parser.parse_args()
    record = build(args.source_root, args.output, args.dependencies_root)
    print(json.dumps({"status": record["status"], "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
