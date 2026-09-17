import hashlib
import zipfile
from pathlib import Path

import pytest

from scripts.prepare_npm import (
    _MAINTAINER_RELEASE_DOCS,
    _replace_tree,
    _stage_wheel,
    _verify_default_requirements,
    _verify_wheel_source,
    _verify_wheel_ui,
)


def test_default_npm_requirements_reject_database_dependencies() -> None:
    _verify_default_requirements(
        "fastapi==1.0.0 \\\n    --hash=sha256:abc\nwebsockets==16.0.0 \\\n    --hash=sha256:def\n"
    )

    for package in ("alembic", "pgvector", "psycopg", "psycopg_binary", "sqlalchemy"):
        with pytest.raises(ValueError, match="database dependencies"):
            _verify_default_requirements(f"{package}==1.0.0 \\\n    --hash=sha256:abc\n")


def test_replace_tree_removes_stale_generated_files(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "package" / "skills"
    source.mkdir()
    destination.mkdir(parents=True)
    (source / "current.toml").write_text('id = "current"\n', encoding="utf-8")
    cache = source / "__pycache__"
    cache.mkdir()
    (cache / "current.pyc").write_bytes(b"local cache")
    (destination / "stale.toml").write_text('id = "stale"\n', encoding="utf-8")

    _replace_tree(source, destination, tmp_path)

    assert [path.name for path in destination.iterdir()] == ["current.toml"]


def test_stage_wheel_removes_only_previous_orqalis_release(tmp_path: Path) -> None:
    vendor = tmp_path / "packages" / "npm" / "vendor"
    vendor.mkdir(parents=True)
    old = vendor / "orqalis-1.0.0-py3-none-any.whl"
    old.write_bytes(b"old release")
    requirements = vendor / "requirements.txt"
    requirements.write_text("existing requirements", encoding="utf-8")
    unrelated = vendor / "another-package-1.0.0-py3-none-any.whl"
    unrelated.write_bytes(b"unrelated")
    wheel = tmp_path / "orqalis-1.0.1-py3-none-any.whl"
    wheel.write_bytes(b"new release")

    _stage_wheel(wheel, vendor, tmp_path)
    _stage_wheel(wheel, vendor, tmp_path)

    assert not old.exists()
    assert (vendor / wheel.name).read_bytes() == b"new release"
    assert requirements.read_text(encoding="utf-8") == "existing requirements"
    assert unrelated.read_bytes() == b"unrelated"


def test_stage_wheel_rejects_vendor_outside_checkout(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    wheel = checkout / "orqalis-1.0.1-py3-none-any.whl"
    wheel.write_bytes(b"new release")
    outside = tmp_path / "outside"

    with pytest.raises(ValueError, match="within the checkout"):
        _stage_wheel(wheel, outside, checkout)
    assert not outside.exists()


def test_wheel_frontend_must_match_current_build_exactly(tmp_path: Path) -> None:
    frontend = tmp_path / "dist"
    assets = frontend / "assets"
    assets.mkdir(parents=True)
    (frontend / "index.html").write_text("<html>current</html>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('current')", encoding="utf-8")
    wheel = tmp_path / "orqalis.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.write(frontend / "index.html", "orqalis/web/index.html")
        archive.write(assets / "app.js", "orqalis/web/assets/app.js")

    with zipfile.ZipFile(wheel) as archive:
        hashes = _verify_wheel_ui(archive, frontend)
    assert hashes == {
        "assets/app.js": hashlib.sha256((assets / "app.js").read_bytes()).hexdigest(),
        "index.html": hashlib.sha256((frontend / "index.html").read_bytes()).hexdigest(),
    }

    (frontend / "extra.css").write_text("stale inventory", encoding="utf-8")
    with zipfile.ZipFile(wheel) as archive, pytest.raises(ValueError, match="inventory is stale"):
        _verify_wheel_ui(archive, frontend)
    (frontend / "extra.css").unlink()

    (frontend / "index.html").write_text("<html>changed</html>", encoding="utf-8")
    with (
        zipfile.ZipFile(wheel) as archive,
        pytest.raises(ValueError, match="Wheel frontend is stale: index.html"),
    ):
        _verify_wheel_ui(archive, frontend)


def test_wheel_python_source_must_match_checkout_exactly(tmp_path: Path) -> None:
    source = tmp_path / "orqalis"
    source.mkdir()
    module = source / "__init__.py"
    module.write_text("version = 1\n", encoding="utf-8")
    wheel = tmp_path / "orqalis.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.write(module, "orqalis/__init__.py")

    with zipfile.ZipFile(wheel) as archive:
        assert _verify_wheel_source(archive, source) == {
            "__init__.py": hashlib.sha256(module.read_bytes()).hexdigest()
        }

    module.write_text("version = 2\n", encoding="utf-8")
    with (
        zipfile.ZipFile(wheel) as archive,
        pytest.raises(ValueError, match="Wheel Python source is stale: __init__.py"),
    ):
        _verify_wheel_source(archive, source)


def test_release_docs_exclude_exact_maintainer_audits_only(tmp_path: Path) -> None:
    source = tmp_path / "docs"
    (source / "verification").mkdir(parents=True)
    for name in (*_MAINTAINER_RELEASE_DOCS, "PUBLISHING.md", "verification/v1.0.0.json"):
        (source / name).write_text("fixture", encoding="utf-8")
    destination = tmp_path / "package" / "docs"
    _replace_tree(source, destination, tmp_path, excluded=_MAINTAINER_RELEASE_DOCS)
    assert sorted(
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file()
    ) == ["PUBLISHING.md", "verification/v1.0.0.json"]


def test_npm_publish_workflow_requires_manual_tag_dispatch_and_oidc() -> None:
    workflow = (Path(__file__).parents[2] / ".github" / "workflows" / "npm-package.yml").read_text(
        encoding="utf-8"
    )
    publish_job = workflow.split("\n  publish:\n", maxsplit=1)[1]

    assert "workflow_dispatch:" in workflow
    assert "default: false" in workflow
    assert "type: boolean" in workflow
    assert "github.event_name == 'workflow_dispatch'" in publish_job
    assert "inputs.publish == true" in publish_job
    assert "startsWith(github.ref, 'refs/tags/v')" in publish_job
    assert "environment: npm-release" in publish_job
    assert "contents: read" in publish_job
    assert "id-token: write" in publish_job
    assert "- smoke" in publish_job
    assert "- installed-integration" in publish_job


def test_npm_publish_workflow_uses_only_the_exact_tested_artifact() -> None:
    workflow = (Path(__file__).parents[2] / ".github" / "workflows" / "npm-package.yml").read_text(
        encoding="utf-8"
    )
    publish_job = workflow.split("\n  publish:\n", maxsplit=1)[1]

    assert "npm install --global npm@12.0.2" in publish_job
    assert "name: orqalis-npm" in publish_job
    assert 'test "${#packages[@]}" -eq 1' in publish_job
    assert "package/package.json" in publish_job
    assert 'test "$package_name" = "orqalis"' in publish_job
    assert 'test "$GITHUB_REF_NAME" = "v$package_version"' in publish_job
    assert 'test "$package" = "dist/orqalis-$package_version.tgz"' in publish_job
    assert 'printf \'package=%s\\n\' "$(realpath "$package")"' in publish_job
    assert "printf 'package=%s\\n' \"$package\"" not in publish_job
    assert (
        'npm publish "${{ steps.release.outputs.package }}" --access public --provenance'
        in publish_job
    )
    assert "NODE_AUTH_TOKEN" not in workflow
    assert "NPM_TOKEN" not in workflow
    assert workflow.count("npm publish") == 1
