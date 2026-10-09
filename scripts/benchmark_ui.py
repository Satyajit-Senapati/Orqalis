"""Measure real local API -> WebSocket -> DOM state transitions on a disposable run."""

from __future__ import annotations

import argparse
import json
import math
import os
import runpy
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any
from uuid import UUID

REPO = Path(__file__).resolve().parents[1]
ACTIVE_OUTPUT: Path | None = None
HELPERS = runpy.run_path(str(REPO / "scripts/benchmark_quality.py"))
BUILD = runpy.run_path(str(REPO / "scripts/build_benchmark_frontend.py"))
TIMINGS = (
    "request_to_http_ms",
    "request_to_snapshot_ms",
    "request_to_event_ms",
    "request_to_dom_ms",
    "snapshot_to_dom_ms",
)


def validate_observations(
    observations: dict[str, Any], run_id: str, initial_state: str, repetitions: int
) -> None:
    if (
        observations["run_id"] != run_id
        or observations["initial_state"] != initial_state
        or len(observations["samples"]) != repetitions * 2
        or observations["page_errors"]
    ):
        raise ValueError("Missing or failed browser observations")
    previous = 0
    command_keys: set[str] = set()
    event_ids: set[str] = set()
    for index, sample in enumerate(observations["samples"]):
        action, expected, kind = (
            ("pause", "PAUSED", "RUN_PAUSED")
            if index % 2 == 0
            else ("resume", initial_state, "RUN_RESUMED")
        )
        if (
            sample["action"] != action
            or sample["expected"] != expected
            or sample["persisted_state"] != expected
            or sample["event_type"] != kind
        ):
            raise ValueError("Unexpected browser state/action witness")
        if any(
            sample[key] != run_id
            for key in (
                "run_id",
                "persisted_run_id",
                "event_run_id",
                "snapshot_run_id",
                "dom_run_id",
            )
        ):
            raise ValueError("Browser witness belongs to a different run")
        command, event_id = sample["command_key"], sample["event_id"]
        UUID(command)
        UUID(event_id)
        if (
            command in command_keys
            or event_id in event_ids
            or sample["event_key"] != f"{command}:run"
        ):
            raise ValueError("Browser witness lacks a unique matching command/event")
        command_keys.add(command)
        event_ids.add(event_id)
        cursors = [
            sample[key]
            for key in (
                "before_sequence",
                "event_sequence",
                "persisted_sequence",
                "snapshot_sequence",
                "dom_sequence",
            )
        ]
        if any(type(cursor) is not int for cursor in cursors):
            raise ValueError("Event cursors must be integers")
        before, event, persisted, snapshot, dom = cursors
        if not (previous <= before < event <= persisted == snapshot == dom):
            raise ValueError("Event/snapshot/DOM cursors do not correlate")
        previous = persisted
        if any(
            type(sample[key]) not in (int, float)
            or not math.isfinite(sample[key])
            or sample[key] < 0
            for key in TIMINGS
        ):
            raise ValueError("Invalid browser timing witness")
        if sample["request_to_event_ms"] > sample["request_to_snapshot_ms"] or not math.isclose(
            sample["request_to_dom_ms"] - sample["request_to_snapshot_ms"],
            sample["snapshot_to_dom_ms"],
            abs_tol=0.001,
        ):
            raise ValueError("Browser timing sequence is inconsistent")


def chrome_executable() -> Path:
    candidates = [
        Path(value) / "Google/Chrome/Application/chrome.exe"
        for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
        if (value := os.environ.get(key))
    ]
    candidates.extend(
        Path(value)
        for name in ("google-chrome", "google-chrome-stable")
        if (value := shutil.which(name))
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError("Installed Chrome executable unavailable")


def main() -> None:
    global ACTIVE_OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--frontend", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--repeat", type=int, help="Pause/resume pairs; default 1 smoke, 3 timing")
    parser.add_argument("--build-evidence", type=Path)
    args = parser.parse_args()
    source, frontend, output = (
        args.source_root.resolve(),
        args.frontend.resolve(),
        args.output.resolve(),
    )
    ACTIVE_OUTPUT = output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "status": "RUNNING",
                "mode": "smoke" if args.smoke else "timing",
                "source_root": str(source),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    evidence = (args.build_evidence or frontend.parent / "build.json").resolve()
    repetitions = args.repeat if args.repeat is not None else (1 if args.smoke else 3)
    if not 1 <= repetitions <= 10:
        raise ValueError("UI repetitions must be between 1 and 10")
    if not args.worker:
        worker = subprocess.run(
            [
                sys.executable,
                "-I",
                str(Path(__file__).resolve()),
                "--worker",
                "--source-root",
                str(source),
                "--frontend",
                str(frontend),
                "--output",
                str(output),
                "--build-evidence",
                str(evidence),
                *(["--smoke"] if args.smoke else []),
                "--repeat",
                str(repetitions),
            ],
            env=HELPERS["controlled_environment"](),
            capture_output=True,
            text=True,
            check=False,
        )
        if worker.returncode:
            raise RuntimeError("UI worker qualification failed:\n" + worker.stderr[-15000:])
        print(worker.stdout, end="")
        return
    build_record = BUILD["validate_build"](source, frontend, evidence)
    before = HELPERS["source_fingerprint"](source)
    input_scripts = [
        Path(__file__).resolve(),
        REPO / "benchmarks/browser_events.mjs",
        REPO / "scripts/benchmark_quality.py",
        REPO / "scripts/build_benchmark_frontend.py",
        evidence,
    ]
    script_hashes = [BUILD["file_hash"](path) for path in input_scripts]
    frontend_before = BUILD["fingerprint"](frontend, artifact=True)
    environment_before = HELPERS["environment_metadata"](repetitions)
    chrome = chrome_executable()
    node = Path(build_record["tools"]["node_path"])
    tool_files = list(
        dict.fromkeys(
            [
                chrome,
                node,
                Path(sys.executable),
                Path(getattr(sys, "_base_executable", sys.executable)),
            ]
        )
    )
    tool_hashes = [BUILD["file_hash"](path) for path in tool_files]
    # Playwright is loaded from the harness repository; bind that actual dependency tree too.
    browser_dependencies = BUILD["fingerprint"](REPO / "web/node_modules", dependencies=True)
    sys.path.insert(0, str(source / "src"))
    import orqalis
    from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
    from orqalis.sdk import Orqalis

    assert Path(orqalis.__file__).resolve().is_relative_to(source / "src")
    with tempfile.TemporaryDirectory(prefix="orqalis-ui-benchmark-") as directory:
        root = Path(directory)
        HELPERS["git"](root, "init", "-b", "main")
        (root / "main.py").write_text("answer = 42\n", encoding="utf-8")
        HELPERS["git"](root, "add", ".")
        HELPERS["git"](root, "commit", "-m", "UI event fixture")
        sdk = Orqalis(root=root)
        project = sdk.initialize(root)
        state = sdk.prepare_run(
            project.id,
            "Observe persisted UI state",
            "feature/ui-event-fixture",
            GoalDraft(
                goal="Observe persisted UI state",
                scope=("main.py",),
                definition_of_done=("State is persisted and rendered",),
                criteria=(
                    CriterionDefinition(
                        key="AC-1",
                        description="Answer exists",
                        validation_spec=FileValidation(path="main.py", contains="42"),
                    ),
                ),
            ),
        )
        sdk.close()
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            port = reserved.getsockname()[1]
        bootstrap = (
            "import sys,importlib;from pathlib import Path;"
            "sys.path.insert(0,sys.argv[1]);import orqalis;"
            "assert Path(orqalis.__file__).resolve().is_relative_to(Path(sys.argv[1]));"
            "module=importlib.import_module('orqalis.api.app');"
            "module.frontend_directory=lambda:Path(sys.argv[3]);import uvicorn;"
            "uvicorn.run(module.create_app(root=Path(sys.argv[2])),host='127.0.0.1',"
            "port=int(sys.argv[4]),log_level='warning')"
        )
        base = f"http://127.0.0.1:{port}"
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW
        with (root / "server.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    bootstrap,
                    str(source / "src"),
                    str(root),
                    str(frontend),
                    str(port),
                ],
                env=HELPERS["controlled_environment"](),
                stdout=log,
                stderr=log,
                creationflags=creationflags,
            )
            try:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError("Owned UI server exited before readiness")
                    try:
                        with urllib.request.urlopen(base + "/api/projects", timeout=1) as response:
                            projects = json.load(response)
                        if any(item["id"] == str(project.id) for item in projects):
                            break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise TimeoutError("Owned UI server failed readiness")
                browser_result = subprocess.run(
                    [
                        str(node),
                        str(REPO / "benchmarks/browser_events.mjs"),
                        str(REPO),
                        base,
                        str(state.run.id),
                        state.run.state.value,
                        str(root / "observations.json"),
                        str(chrome),
                        str(repetitions),
                    ],
                    env=HELPERS["controlled_environment"](),
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if browser_result.returncode:
                    raise RuntimeError(
                        "Browser correlation failed:\n"
                        + browser_result.stderr[-12000:]
                        + "\nOwned server log:\n"
                        + (root / "server.log").read_text(encoding="utf-8")[-6000:]
                    )
                observations = json.loads((root / "observations.json").read_text())
            finally:
                if process.poll() is None:
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                            capture_output=True,
                            check=False,
                            timeout=15,
                        )
                    else:
                        process.terminate()
                    process.wait(timeout=10)
    validate_observations(observations, str(state.run.id), state.run.state.value, repetitions)
    stable = (
        before == HELPERS["source_fingerprint"](source)
        and frontend_before == BUILD["fingerprint"](frontend, artifact=True)
        and script_hashes == [BUILD["file_hash"](path) for path in input_scripts]
        and tool_hashes == [BUILD["file_hash"](path) for path in tool_files]
        and environment_before == HELPERS["environment_metadata"](repetitions)
        and browser_dependencies
        == BUILD["fingerprint"](REPO / "web/node_modules", dependencies=True)
        and build_record == BUILD["validate_build"](source, frontend, evidence)
    )
    distribution = (
        None
        if args.smoke
        else HELPERS["distribution"](
            [sample["request_to_dom_ms"] for sample in observations["samples"]]
        )
    )
    if args.smoke:
        for sample in observations["samples"]:
            for key in TIMINGS:
                sample[key] = None
    report = {
        "schema_version": 2,
        "mode": "smoke" if args.smoke else "timing",
        "source_sha256": before["sha256"],
        "source_inventory": before["files"],
        "source_stable": stable,
        "frontend_sha256": frontend_before["sha256"],
        "frontend_inventory": frontend_before["files"],
        "frontend_build": {
            "record": build_record,
            "evidence_path": str(evidence),
            "evidence_sha256": script_hashes[-1],
            "source_web_sha256": build_record["source_web"]["sha256"],
            "dependency_sha256": build_record["dependencies"]["sha256"],
            "method": build_record["method"],
        },
        "script_inputs": {
            str(path): digest for path, digest in zip(input_scripts, script_hashes, strict=True)
        },
        "tool_inputs": {
            str(path): digest for path, digest in zip(tool_files, tool_hashes, strict=True)
        },
        "browser_dependency_sha256": browser_dependencies["sha256"],
        "environment": environment_before,
        **observations,
        "request_to_dom": distribution,
        "scope": (
            "Warm local pause/resume API through real WebSocket to DOM; exact run, command, "
            "durable event and rendered sequence correlation. No provider/network generalization. "
            "Smoke mode suppresses timing output."
        ),
        "status": "PASS" if stable else "FAIL",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "status": report["status"],
                "request_to_dom": report["request_to_dom"],
            },
            indent=2,
        )
    )
    if not stable:
        raise RuntimeError("Source, frontend or harness changed during capture")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if ACTIVE_OUTPUT is not None:
            try:
                failed_report = json.loads(ACTIVE_OUTPUT.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                failed_report = {}
            failed_report.update(status="FAIL", error=str(error))
            ACTIVE_OUTPUT.write_text(json.dumps(failed_report, indent=2) + "\n", encoding="utf-8")
        raise
