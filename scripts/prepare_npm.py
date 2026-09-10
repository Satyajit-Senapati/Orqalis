"""Stage a verified release wheel and hash-locked runtime dependencies for npm."""

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path


def prepare(root: Path, uv: str) -> None:
    package = root / "packages" / "npm"
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    npm = json.loads((package / "package.json").read_text(encoding="utf-8"))
    version = config["version"]
    frontend = json.loads((root / "web/package.json").read_text(encoding="utf-8"))
    if frontend["version"] != version:
        raise ValueError("Frontend and Python release versions must match")
    if npm["version"] != version or npm["license"] != config["license"]:
        raise ValueError("Python and npm version/license must match")
    wheel = root / ".tools" / "release" / f"orqalis-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel) as archive:
        metadata = BytesParser().parsebytes(archive.read(f"orqalis-{version}.dist-info/METADATA"))
        if metadata["Version"] != version or metadata["License-Expression"] != config["license"]:
            raise ValueError("Rebuild the wheel: version or license metadata is stale")
        module = ast.parse(archive.read("orqalis/__init__.py").decode())
        versions = [
            ast.literal_eval(node.value)
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__version__"
                for target in node.targets
            )
        ]
        if versions != [version]:
            raise ValueError("Wheel's runtime version does not match release metadata")
        names = archive.namelist()
        for required in (
            "orqalis/web/index.html",
            "orqalis/web/THIRD_PARTY_NOTICES.txt",
            f"orqalis-{version}.dist-info/licenses/LICENSE",
        ):
            if required not in names:
                raise ValueError(f"Wheel is missing {required}")
        if not any("/versions/" in name and name.endswith(".py") for name in names):
            raise ValueError("Wheel must contain migrations")
    vendor = package / "vendor"
    vendor.mkdir(exist_ok=True)
    # Explicit paths avoid accidentally shipping an older release from dist/.
    shutil.copy2(wheel, vendor / wheel.name)
    subprocess.run(
        [
            uv,
            "export",
            "--locked",
            "--no-dev",
            "--no-emit-project",
            "--no-header",
            "--no-annotate",
            "--format",
            "requirements.txt",
            "--output-file",
            str(vendor / "requirements.txt"),
        ],
        cwd=root,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    requirements = (vendor / "requirements.txt").read_text(encoding="utf-8")
    if "--hash=sha256:" not in requirements or any(
        marker in requirements for marker in ("file://", " @ ", "--index-url", "--extra-index-url")
    ):
        raise ValueError("Dependencies must use pinned, hashed registry distributions")
    manifest = {
        "schema": 1,
        "version": version,
        "license": config["license"],
        "files": {
            name: hashlib.sha256((vendor / name).read_bytes()).hexdigest()
            for name in (wheel.name, "requirements.txt")
        },
    }
    (vendor / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for name in ("LICENSE", "README.md", "SIGNOFF.md", "compose.yaml"):
        shutil.copy2(root / name, package / name)
    (package / "GUIDE.md").unlink(missing_ok=True)
    # Regenerate copied docs so removed installation routes cannot survive repacking.
    docs = package / "docs"
    if docs.is_symlink() or not docs.resolve().is_relative_to(root.resolve()):
        raise ValueError("Generated documentation path must remain within the checkout")
    if docs.exists():
        shutil.rmtree(docs)
    shutil.copytree(root / "docs", docs)
    skill_path = Path("src/orqalis/skills/bundled")
    shutil.copytree(root / skill_path, package / skill_path, dirs_exist_ok=True)
    print(f"Prepared npm release {version}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default="uv", help="uv executable used to export uv.lock")
    arguments = parser.parse_args()
    prepare(Path(__file__).resolve().parents[1], arguments.uv)
