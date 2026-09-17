import csv
import json
import os
import stat
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from orqalis.diagnostics import CheckStatus, diagnose_project
from orqalis.persistence.filesystem.io import atomic_write_json
from orqalis.persistence.filesystem.layout import (
    ProjectLayout,
    bootstrap_project_store,
    load_manifest,
)


def statuses(report) -> dict[str, CheckStatus]:  # type: ignore[no-untyped-def]
    return {check.name: check.status for check in report.checks}


def test_doctor_reports_uninitialized_project(tmp_path: Path) -> None:
    report = diagnose_project(tmp_path)
    assert report.healthy is False
    assert statuses(report) == {"store": CheckStatus.FAIL}


def test_doctor_accepts_missing_rebuildable_data(tmp_path: Path) -> None:
    layout = bootstrap_project_store(tmp_path)
    report = diagnose_project(tmp_path)

    assert report.healthy is True
    assert report.schema_version == 2
    assert statuses(report)["manifest"] == CheckStatus.PASS
    assert statuses(report)["project_identity"] == CheckStatus.WARN
    assert statuses(report)["index"] == CheckStatus.WARN
    assert statuses(report)["cache"] == CheckStatus.WARN
    assert layout.manifest.is_file()


def test_doctor_reports_genuinely_read_only_project_store(tmp_path: Path) -> None:
    layout = bootstrap_project_store(tmp_path)
    original_mode = stat.S_IMODE(layout.store.stat().st_mode)
    probe = layout.store / ".write-probe"
    denied_sid: str | None = None
    if os.name == "nt":
        identity = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"],
            check=True,
            capture_output=True,
            text=True,
        )
        denied_sid = next(csv.reader([identity.stdout.strip()]))[1]
        restriction = subprocess.run(
            ["icacls", str(layout.store), "/deny", f"*{denied_sid}:(W)"],
            check=False,
            capture_output=True,
        )
        if restriction.returncode:
            pytest.skip("This Windows filesystem does not support a temporary deny-write ACL")
    else:
        os.chmod(layout.store, stat.S_IREAD | stat.S_IEXEC)
    try:
        try:
            probe.write_bytes(b"probe")
        except OSError:
            pass
        else:
            probe.unlink()
            pytest.skip("This filesystem does not enforce read-only directory modes")

        report = diagnose_project(tmp_path)

        assert report.healthy is False
        assert statuses(report)["writable"] == CheckStatus.FAIL
    finally:
        if denied_sid is not None:
            subprocess.run(
                ["icacls", str(layout.store), "/remove:d", f"*{denied_sid}"],
                check=True,
                capture_output=True,
            )
        else:
            os.chmod(layout.store, original_mode)
        probe.unlink(missing_ok=True)


def test_doctor_rejects_invalid_config(tmp_path: Path) -> None:
    layout = bootstrap_project_store(tmp_path)
    layout.config.write_text("not json", encoding="utf-8")

    report = diagnose_project(tmp_path)
    assert report.healthy is False
    assert statuses(report)["config"] == CheckStatus.FAIL


def test_doctor_validates_task_event_sequences(tmp_path: Path) -> None:
    layout = bootstrap_project_store(tmp_path)
    capsule = layout.tasks / "ORQ-20260916-0001"
    atomic_write_json(
        capsule / "task.yaml",
        {
            "schema_version": 1,
            "id": capsule.name,
            "run_id": str(uuid4()),
        },
    )
    events = capsule / "execution" / "events.jsonl"
    events.parent.mkdir(parents=True)
    events.write_text(json.dumps({"sequence": 2}) + "\n", encoding="utf-8")

    report = diagnose_project(tmp_path)
    assert report.healthy is False
    assert statuses(report)["tasks"] == CheckStatus.FAIL


def test_doctor_rejects_machine_specific_project_identity(tmp_path: Path) -> None:
    project_id = uuid4()
    bootstrap_project_store(tmp_path, project_id=project_id)
    atomic_write_json(
        ProjectLayout(tmp_path).project / "identity.yaml",
        {"schema_version": 1, "id": str(project_id), "repo_root": str(tmp_path)},
    )

    report = diagnose_project(tmp_path)
    assert report.healthy is False
    assert statuses(report)["project_identity"] == CheckStatus.FAIL


def test_doctor_migrates_schema_one_before_validation(tmp_path: Path) -> None:
    layout = bootstrap_project_store(tmp_path)
    current = load_manifest(layout)
    old = {
        "schema_version": 1,
        "project": current["project"],
        "initialized_at": current["initialized_at"],
        "graph": {"indexed_commit": "abc123", "indexed_branch": "main"},
    }
    atomic_write_json(layout.manifest, old)
    original_manifest = layout.manifest.read_bytes()
    summary = b"# Existing project summary\n"
    layout.project.mkdir(parents=True, exist_ok=True)
    (layout.project / "summary.md").write_bytes(summary)

    report = diagnose_project(tmp_path)

    assert report.healthy is True
    assert report.schema_version == 2
    manifest_check = next(check for check in report.checks if check.name == "manifest")
    assert manifest_check.status == CheckStatus.PASS
    assert "Migrated filesystem schema 1" in manifest_check.message
    assert (layout.project / "summary.md").read_bytes() == summary
    backups = tuple((layout.store / "backups").glob("manifest.schema-1.*.yaml"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == original_manifest
