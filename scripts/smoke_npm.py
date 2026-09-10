"""Exercise the installed npm tarball outside the source checkout, without a database."""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


def smoke(prefix: Path, runtime: Path | None) -> None:
    modules = prefix / ("node_modules" if os.name == "nt" else "lib/node_modules")
    package = modules / "orqalis"
    launcher = package / "bin" / "orqalis.js"
    manifest = json.loads((package / "package.json").read_text(encoding="utf-8"))
    env = dict(os.environ)
    if runtime:
        env["ORQALIS_RUNTIME_HOME"] = str(runtime.resolve())
    with tempfile.TemporaryDirectory(prefix="orqalis-npm-smoke-") as directory:
        cwd = Path(directory)
        # A project's same-named module must not shadow the installed backend.
        (cwd / "orqalis.py").write_text("raise RuntimeError('cwd module executed')\n")
        command = ["node", str(launcher)]
        version = subprocess.run(
            [*command, "version"], cwd=cwd, env=env, capture_output=True, text=True, timeout=900
        )
        if version.returncode != 0 or version.stdout.strip() != manifest["version"]:
            raise RuntimeError(f"Cold launch failed: {version.stdout}\n{version.stderr}")
        cached = subprocess.run(
            [*command, "version"], cwd=cwd, env=env, capture_output=True, text=True, timeout=60
        )
        assert cached.returncode == 0 and cached.stdout.strip() == manifest["version"]
        assert "preparing isolated" not in cached.stderr
        capabilities = subprocess.run(
            [*command, "capabilities"], cwd=cwd, env=env, capture_output=True, text=True, timeout=60
        )
        assert capabilities.returncode == 0, capabilities.stderr
        assert json.loads(capabilities.stdout)
        invalid = subprocess.run(
            [*command, "not-a-command"],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert invalid.returncode == 2
    print(
        json.dumps(
            {
                "version": manifest["version"],
                "cold_launch": "PASS",
                "cached_launch": "PASS",
                "json_stdout": "PASS",
                "invalid_exit_code": "PASS",
                "cwd_isolation": "PASS",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--runtime", type=Path)
    args = parser.parse_args()
    smoke(args.prefix.resolve(), args.runtime)
