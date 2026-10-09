"""Adversarial calibration for frontend provenance and correlated browser evidence."""

from __future__ import annotations

import copy
import json
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

REPO = Path(__file__).resolve().parents[2]
BUILD = runpy.run_path(str(REPO / "scripts/build_benchmark_frontend.py"))
UI = runpy.run_path(str(REPO / "scripts/benchmark_ui.py"))


def observations() -> dict[str, Any]:
    run_id = str(uuid4())
    samples = []
    for index, (action, expected, kind) in enumerate(
        (("pause", "PAUSED", "RUN_PAUSED"), ("resume", "EXECUTING", "RUN_RESUMED"))
    ):
        command = str(uuid4())
        sample = {
            "action": action,
            "expected": expected,
            "persisted_state": expected,
            "event_type": kind,
            "command_key": command,
            "event_key": f"{command}:run",
            "event_id": str(uuid4()),
            "before_sequence": 10 + index * 3,
            "event_sequence": 11 + index * 3,
            "persisted_sequence": 13 + index * 3,
            "snapshot_sequence": 13 + index * 3,
            "dom_sequence": 13 + index * 3,
            "request_to_http_ms": 4,
            "request_to_event_ms": 2,
            "request_to_snapshot_ms": 3,
            "request_to_dom_ms": 5,
            "snapshot_to_dom_ms": 2,
        }
        sample.update(
            dict.fromkeys(
                ("run_id", "persisted_run_id", "event_run_id", "snapshot_run_id", "dom_run_id"),
                run_id,
            )
        )
        samples.append(sample)
    return {"run_id": run_id, "initial_state": "EXECUTING", "samples": samples, "page_errors": []}


def test_correlated_browser_witness_accepts_exact_run_event_and_rendered_cursor() -> None:
    data = observations()
    UI["validate_observations"](data, data["run_id"], "EXECUTING", 1)


@pytest.mark.parametrize(
    "key,value",
    [
        ("event_run_id", "wrong-run"),
        ("snapshot_run_id", "wrong-run"),
        ("dom_run_id", "wrong-run"),
        ("persisted_run_id", "wrong-run"),
        ("event_key", "unrelated:run"),
        ("event_type", "RUN_CREATED"),
        ("event_sequence", 10),
        ("snapshot_sequence", 14),
        ("dom_sequence", 12),
        ("before_sequence", True),
        ("request_to_http_ms", float("nan")),
        ("request_to_event_ms", 4),
        ("snapshot_to_dom_ms", 0),
        ("persisted_state", "FAILED"),
    ],
)
def test_browser_witness_rejects_mismatched_or_nonfinite_evidence(key: str, value: Any) -> None:
    data = observations()
    data["samples"][0][key] = value
    with pytest.raises(ValueError):
        UI["validate_observations"](data, data["run_id"], "EXECUTING", 1)


def test_browser_witness_rejects_replayed_command_or_event() -> None:
    data = observations()
    data["samples"][1]["event_id"] = data["samples"][0]["event_id"]
    with pytest.raises(ValueError, match="unique"):
        UI["validate_observations"](data, data["run_id"], "EXECUTING", 1)


@pytest.fixture
def build_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    web = tmp_path / "source/web"
    web.mkdir(parents=True)
    (web / "package-lock.json").write_text("lock")
    (web / "src").mkdir()
    (web / "src/app.tsx").write_text("export const revision = 'selected'")
    dependency = tmp_path / "dependencies"
    (dependency / "node_modules").mkdir(parents=True)
    (dependency / "package-lock.json").write_text("lock")
    (dependency / "node_modules/tool.js").write_text("exact tool")
    frontend = tmp_path / "build/dist"
    frontend.mkdir(parents=True)
    (frontend / "index.html").write_text("<html>selected artifact</html>")
    tools = {"node_path": "node", "node_sha256": "toolhash", "node_version": "v1"}
    monkeypatch.setitem(BUILD["validate_build"].__globals__, "tools_fingerprint", lambda _: tools)
    record = {
        "schema_version": 1,
        "method": "isolated-copy-v1",
        "status": "PASS",
        "pipeline": BUILD["PIPELINE"],
        "source_web": BUILD["fingerprint"](web),
        "artifact": BUILD["fingerprint"](frontend, artifact=True),
        "dependency_root": str(dependency),
        "dependency_lock_sha256": BUILD["file_hash"](dependency / "package-lock.json"),
        "dependencies": BUILD["fingerprint"](dependency / "node_modules", dependencies=True),
        "tools": tools,
        "builder_sha256": BUILD["file_hash"](REPO / "scripts/build_benchmark_frontend.py"),
    }
    evidence = frontend.parent / "build.json"
    evidence.write_text(json.dumps(record))
    return web.parent, frontend, evidence


def test_build_evidence_accepts_exact_inputs(build_evidence: tuple[Path, Path, Path]) -> None:
    assert BUILD["validate_build"](*build_evidence)["status"] == "PASS"


@pytest.mark.parametrize("target", ["source", "artifact", "extra_artifact", "dependency", "lock"])
def test_build_evidence_rejects_wrong_revision_or_changed_inputs(
    build_evidence: tuple[Path, Path, Path],
    target: str,
) -> None:
    source, frontend, evidence = build_evidence
    record = json.loads(evidence.read_text())
    paths = {
        "source": source / "web/src/app.tsx",
        "artifact": frontend / "index.html",
        "extra_artifact": frontend / "unbound.js",
        "dependency": Path(record["dependency_root"]) / "node_modules/tool.js",
        "lock": Path(record["dependency_root"]) / "package-lock.json",
    }
    paths[target].write_text("different revision")
    with pytest.raises(ValueError):
        BUILD["validate_build"](*build_evidence)


def test_build_evidence_rejects_unqualified_manifest(
    build_evidence: tuple[Path, Path, Path],
) -> None:
    source, frontend, evidence = build_evidence
    record = copy.deepcopy(json.loads(evidence.read_text()))
    record["status"] = "FAIL"
    evidence.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="not qualified"):
        BUILD["validate_build"](source, frontend, evidence)


def test_web_inventory_keeps_source_subdirectories_named_like_generated_outputs(
    tmp_path: Path,
) -> None:
    (tmp_path / "src/dist").mkdir(parents=True)
    (tmp_path / "src/dist/component.tsx").write_text("real source")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist/generated.js").write_text("prior build")
    assert BUILD["fingerprint"](tmp_path)["files"] == ["src/dist/component.tsx"]


def test_failed_capture_replaces_previous_pass_report(tmp_path: Path) -> None:
    output = tmp_path / "capture.json"
    output.write_text('{"status":"PASS","old_capture":true}')
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            str(REPO / "scripts/benchmark_ui.py"),
            "--source-root",
            str(tmp_path / "source"),
            "--frontend",
            str(tmp_path / "dist"),
            "--output",
            str(output),
            "--smoke",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode != 0
    report = json.loads(output.read_text())
    assert report["status"] == "FAIL"
    assert "old_capture" not in report
    assert "build.json" in report["error"]
