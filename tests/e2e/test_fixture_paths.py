from pathlib import Path

import pytest

from tests.e2e.fixture_paths import WORKSPACE_ROOT, fixture_root


def test_fixture_root_uses_configured_external_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    configured = tmp_path / "dashboard-fixtures"
    monkeypatch.setenv("ORQALIS_QA_FIXTURE_ROOT", str(configured))

    assert fixture_root() == configured.resolve()
    assert configured.is_dir()


def test_fixture_root_rejects_workspace_descendants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ORQALIS_QA_FIXTURE_ROOT", str(WORKSPACE_ROOT / ".tools" / "fixtures"))

    with pytest.raises(RuntimeError, match="must be outside"):
        fixture_root()
