import hashlib
import zipfile
from pathlib import Path

import pytest

from scripts.prepare_npm import (
    _MAINTAINER_RELEASE_DOCS,
    _replace_tree,
    _verify_wheel_source,
    _verify_wheel_ui,
)


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
