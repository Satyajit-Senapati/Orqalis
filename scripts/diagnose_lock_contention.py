"""Instrument an unchanged concurrency contract; never alter lock policy or timeout.

Use the same frozen --tests-root for both sources. This is a diagnostic, not a
performance benchmark: in-memory timing instrumentation changes scheduling.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import runpy
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

NODE = (
    "tests/integration/test_runtime.py::"
    "test_event_sequence_concurrency_idempotency_and_corruption_detection"
)
FIXTURE_FILES = (
    "pyproject.toml",
    "tests/__init__.py",
    "tests/conftest.py",
    "tests/support/filesystem.py",
    "tests/integration/test_runtime.py",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--tests-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source, fixture, output = (
        args.source_root.resolve(),
        args.tests_root.resolve(),
        args.output.resolve(),
    )
    script = Path(__file__).resolve()
    helper = script.with_name("benchmark_quality.py")
    helpers = runpy.run_path(str(helper))
    if not args.worker:
        raise SystemExit(
            subprocess.run(
                [sys.executable, "-I", str(script), *sys.argv[1:], "--worker"],
                env=helpers["controlled_environment"](),
                check=False,
            ).returncode
        )
    before = helpers["source_fingerprint"](source)
    fixture_hash = helpers["digest_files"](fixture, list(FIXTURE_FILES))
    script_hash = hashlib.sha256(script.read_bytes()).hexdigest()
    helper_hash = hashlib.sha256(helper.read_bytes()).hexdigest()
    sys.path[:0] = [str(source / "src"), str(fixture)]
    import pytest

    import orqalis
    from orqalis.persistence.filesystem.locking import FileLock

    assert Path(orqalis.__file__).resolve().is_relative_to(source / "src")
    events: list[dict[str, Any]] = []
    event_guard = threading.Lock()
    origin = time.perf_counter_ns()

    def record(kind: str, **fields: Any) -> None:
        item = {
            "kind": kind,
            "ns": time.perf_counter_ns() - origin,
            "thread": threading.get_ident(),
            "thread_name": threading.current_thread().name,
            **fields,
        }
        with event_guard:
            events.append(item)

    original_acquire, original_release, original_fsync = (
        FileLock.acquire,
        FileLock.release,
        os.fsync,
    )

    def acquire(lock: FileLock) -> None:
        fields = {"path": str(lock.path), "lock": id(lock), "timeout": lock.timeout}
        record("acquire_start", **fields)
        start = time.perf_counter_ns()
        try:
            original_acquire(lock)
        except BaseException as exc:
            record(
                "acquire_error",
                wait_ns=time.perf_counter_ns() - start,
                error=type(exc).__name__,
                **fields,
            )
            raise
        record(
            "acquired", wait_ns=time.perf_counter_ns() - start, depth=lock._state.depth, **fields
        )

    def release(lock: FileLock) -> None:
        fields = {"path": str(lock.path), "lock": id(lock)}
        record("release_start", depth=lock._state.depth, **fields)
        original_release(lock)
        record("released", **fields)

    def fsync(fd: int) -> None:
        start = time.perf_counter_ns()
        try:
            original_fsync(fd)
        finally:
            record("fsync", elapsed_ns=time.perf_counter_ns() - start)

    output.parent.mkdir(parents=True, exist_ok=True)
    patch = pytest.MonkeyPatch()
    patch.setattr(FileLock, "acquire", acquire)
    patch.setattr(FileLock, "release", release)
    patch.setattr(os, "fsync", fsync)
    started = time.perf_counter()
    try:
        code = pytest.main(
            [
                "-q",
                "-o",
                "addopts=",
                "--rootdir",
                str(fixture),
                "--confcutdir",
                str(fixture),
                "--junitxml",
                str(output.with_suffix(".xml")),
                str(fixture / NODE),
            ]
        )
    finally:
        patch.undo()
    elapsed = time.perf_counter() - started
    bad_imports = [
        name
        for name, module in sys.modules.items()
        if (name == "orqalis" or name.startswith("orqalis."))
        and (module_path := getattr(module, "__file__", None))
        and not Path(module_path).resolve().is_relative_to(source / "src")
    ]
    active: dict[tuple[int, int], list[int]] = {}
    holds = []
    for event in events:
        if event["kind"] == "acquired":
            active.setdefault((event["thread"], event["lock"]), []).append(event["ns"])
        elif event["kind"] == "release_start":
            stack = active.get((event["thread"], event["lock"]), [])
            if stack:
                holds.append({**event, "hold_ns": event["ns"] - stack.pop()})
    acquisitions = [e for e in events if e["kind"] == "acquired"]
    failures = [e for e in events if e["kind"] == "acquire_error"]
    report = {
        "schema_version": 1,
        "scope": "instrumented unchanged contract; no timing/performance acceptance claim",
        "source_root": str(source),
        "source_sha256": before["sha256"],
        "source_stable": before == helpers["source_fingerprint"](source),
        "fixture_sha256": fixture_hash,
        "fixture_stable": fixture_hash == helpers["digest_files"](fixture, list(FIXTURE_FILES)),
        "script_sha256": script_hash,
        "script_stable": script_hash == hashlib.sha256(script.read_bytes()).hexdigest(),
        "helper_sha256": helper_hash,
        "helper_stable": helper_hash == hashlib.sha256(helper.read_bytes()).hexdigest(),
        "environment": helpers["environment_metadata"](1),
        "bad_imports": bad_imports,
        "pytest_exit_code": int(code),
        "elapsed_s": elapsed,
        "maximum_wait_s": max((e["wait_ns"] / 1e9 for e in acquisitions), default=0),
        "maximum_hold_s": max((e["hold_ns"] / 1e9 for e in holds), default=0),
        "acquisition_failures": failures,
        "unreleased_acquisitions": sum(map(len, active.values())),
        "events": events,
        "holds": holds,
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "pytest_exit_code",
                    "elapsed_s",
                    "maximum_wait_s",
                    "maximum_hold_s",
                    "source_stable",
                    "fixture_stable",
                    "bad_imports",
                    "acquisition_failures",
                    "unreleased_acquisitions",
                )
            }
        )
    )
    if (
        code
        or bad_imports
        or not all(
            report[key]
            for key in (
                "source_stable",
                "fixture_stable",
                "script_stable",
                "helper_stable",
            )
        )
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
