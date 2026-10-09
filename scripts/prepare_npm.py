"""Stage a verified release wheel and hash-locked runtime dependencies for npm."""

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
import tomllib
import urllib.request
import zipfile
from email.parser import BytesParser
from pathlib import Path

_MAINTAINER_RELEASE_DOCS = frozenset(
    {
        "quality",
        "NPM_RELEASE_READINESS.md",
        "REPOSITORY_CLEANUP_AUDIT.md",
        "verification/npm-release-readiness.json",
    }
)

_DATABASE_PACKAGES = frozenset({"alembic", "pgvector", "psycopg", "psycopg-binary", "sqlalchemy"})

_IGNORED_RELEASE_ARTIFACTS = shutil.ignore_patterns(
    "__pycache__", "*.pyc", "*.pyo", ".DS_Store", "Thumbs.db"
)


def _is_ignored_release_artifact(path: Path) -> bool:
    return (
        "__pycache__" in path.parts
        or path.name in {".DS_Store", "Thumbs.db"}
        or path.suffix in {".pyc", ".pyo"}
    )


def _tree_files(root: Path, *, ignore_artifacts: bool = False) -> dict[str, Path]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"Release source must be a real directory: {root}")
    files: dict[str, Path] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ignore_artifacts and _is_ignored_release_artifact(relative):
            continue
        if path.is_symlink():
            raise ValueError(f"Release source cannot contain symlinks: {path}")
        if path.is_file():
            files[relative.as_posix()] = path
    return files


def _verify_wheel_ui(archive: zipfile.ZipFile, frontend: Path) -> dict[str, str]:
    source = _tree_files(frontend)
    prefix = "orqalis/web/"
    packaged = {
        name.removeprefix(prefix): name
        for name in archive.namelist()
        if name.startswith(prefix) and not name.endswith("/")
    }
    if source.keys() != packaged.keys():
        missing = sorted(source.keys() - packaged.keys())
        extra = sorted(packaged.keys() - source.keys())
        raise ValueError(f"Wheel frontend inventory is stale (missing={missing}, extra={extra})")
    hashes: dict[str, str] = {}
    for name, path in source.items():
        content = path.read_bytes()
        if archive.read(packaged[name]) != content:
            raise ValueError(f"Wheel frontend is stale: {name}")
        hashes[name] = hashlib.sha256(content).hexdigest()
    return hashes


def _verify_wheel_source(archive: zipfile.ZipFile, source_root: Path) -> dict[str, str]:
    source = _tree_files(source_root, ignore_artifacts=True)
    prefix = "orqalis/"
    packaged = {
        name.removeprefix(prefix): name
        for name in archive.namelist()
        if name.startswith(prefix)
        and not name.startswith("orqalis/web/")
        and not name.endswith("/")
    }
    if source.keys() != packaged.keys():
        missing = sorted(source.keys() - packaged.keys())
        extra = sorted(packaged.keys() - source.keys())
        raise ValueError(f"Wheel Python inventory is stale (missing={missing}, extra={extra})")
    hashes: dict[str, str] = {}
    for name, path in source.items():
        content = path.read_bytes()
        if archive.read(packaged[name]) != content:
            raise ValueError(f"Wheel Python source is stale: {name}")
        hashes[name] = hashlib.sha256(content).hexdigest()
    return hashes


def _replace_tree(
    source: Path, destination: Path, checkout: Path, *, excluded: frozenset[str] = frozenset()
) -> None:
    _tree_files(source, ignore_artifacts=True)
    target = destination.resolve()
    boundary = checkout.resolve()
    if destination.is_symlink() or target == boundary or not target.is_relative_to(boundary):
        raise ValueError("Generated release path must remain within the checkout")
    if destination.exists():
        if not destination.is_dir():
            raise ValueError(f"Generated release path must be a directory: {destination}")
        shutil.rmtree(destination)

    def ignore(directory: str, names: list[str]) -> set[str]:
        return _IGNORED_RELEASE_ARTIFACTS(directory, names) | {
            name
            for name in names
            if (Path(directory) / name).relative_to(source).as_posix() in excluded
        }

    shutil.copytree(source, destination, ignore=ignore)


def _stage_wheel(wheel: Path, vendor: Path, checkout: Path) -> None:
    """Replace the generated wheel without carrying older releases into npm pack."""
    boundary = checkout.resolve()
    target = vendor.resolve()
    if vendor.is_symlink() or target == boundary or not target.is_relative_to(boundary):
        raise ValueError("Generated release path must remain within the checkout")
    vendor.mkdir(exist_ok=True)
    if not vendor.is_dir():
        raise ValueError(f"Generated release path must be a directory: {vendor}")
    current = vendor / wheel.name
    if current.is_symlink():
        raise ValueError(f"Generated release wheel cannot be a symlink: {current}")
    shutil.copy2(wheel, current)
    for stale in vendor.glob("orqalis-*-py3-none-any.whl"):
        if stale == current:
            continue
        if stale.is_symlink() or not stale.is_file():
            raise ValueError(f"Generated release wheel must be a regular file: {stale}")
        stale.unlink()


def _verify_default_requirements(requirements: str) -> None:
    """Reject database packages in the standard repo-local npm runtime."""

    packages = {
        line.partition("==")[0].strip().lower().replace("_", "-")
        for line in requirements.splitlines()
        if "==" in line and not line[:1].isspace()
    }
    leaked = sorted(packages & _DATABASE_PACKAGES)
    if leaked:
        raise ValueError("Default npm runtime includes database dependencies: " + ", ".join(leaked))


def _stage_bootstrap_pip(root: Path, vendor: Path) -> dict[str, str]:
    """Bundle the exact locked pip wheel before the launcher makes any network install."""
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    group = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))[
        "dependency-groups"
    ]["bootstrap"]
    packages = [p for p in lock["package"] if p["name"] == "pip"]
    if len(packages) != 1 or group != [f"pip=={packages[0]['version']}"]:
        raise ValueError("Bootstrap pip must have one exact locked version")
    package = packages[0]
    name = f"pip-{package['version']}-py3-none-any.whl"
    wheels = [w for w in package["wheels"] if w["url"].endswith("/" + name)]
    if len(wheels) != 1 or not wheels[0]["url"].startswith("https://files.pythonhosted.org/"):
        raise ValueError("Bootstrap pip requires one trusted registry wheel")
    locked = wheels[0]
    expected = locked["hash"].removeprefix("sha256:")
    destination = vendor / name
    if destination.is_symlink():
        raise ValueError("Bootstrap wheel cannot be a symlink")
    if destination.exists():
        content = destination.read_bytes()
    else:
        with urllib.request.urlopen(locked["url"], timeout=60) as response:
            content = response.read()
    if hashlib.sha256(content).hexdigest() != expected or len(content) != locked["size"]:
        raise ValueError("Bootstrap pip wheel integrity check failed")
    destination.write_bytes(content)
    for stale in vendor.glob("pip-*-py3-none-any.whl"):
        if stale != destination:
            if stale.is_symlink() or not stale.is_file():
                raise ValueError("Bootstrap wheel must be a regular file")
            stale.unlink()
    return {"version": package["version"], "wheel": name}


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
        source = _verify_wheel_source(archive, root / "src" / "orqalis")
        web = _verify_wheel_ui(archive, root / "web" / "dist")
    vendor = package / "vendor"
    # Explicit paths avoid accidentally shipping an older release from dist/.
    _stage_wheel(wheel, vendor, root)
    bootstrap = _stage_bootstrap_pip(root, vendor)
    subprocess.run(
        [
            uv,
            "export",
            "--locked",
            "--no-dev",
            "--group",
            "bootstrap",
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
    _verify_default_requirements(requirements)
    manifest = {
        "schema": 1,
        "version": version,
        "license": config["license"],
        "bootstrap": bootstrap,
        "files": {
            name: hashlib.sha256((vendor / name).read_bytes()).hexdigest()
            for name in (wheel.name, bootstrap["wheel"], "requirements.txt")
        },
        "web": web,
        "source": source,
        "build_inputs": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ("pyproject.toml", "uv.lock", "hatch_build.py")
        },
    }
    (vendor / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for name in ("LICENSE", "README.md", "SIGNOFF.md"):
        shutil.copy2(root / name, package / name)
    (package / "GUIDE.md").unlink(missing_ok=True)
    # Regenerate copied docs so removed installation routes cannot survive repacking.
    _replace_tree(root / "docs", package / "docs", root, excluded=_MAINTAINER_RELEASE_DOCS)
    skill_path = Path("src/orqalis/skills/bundled")
    _replace_tree(root / skill_path, package / skill_path, root)
    output = root / "dist"
    if output.is_symlink() or not output.resolve().is_relative_to(root.resolve()):
        raise ValueError("Release output directory must remain within the checkout")
    if output.exists() and not output.is_dir():
        raise ValueError("Release output path must be a directory")
    output.mkdir(exist_ok=True)
    print(f"Prepared npm release {version}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default="uv", help="uv executable used to export uv.lock")
    arguments = parser.parse_args()
    prepare(Path(__file__).resolve().parents[1], arguments.uv)
