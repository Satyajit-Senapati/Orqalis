"""Qualify a bounded local workload under a Windows job memory cap and one CPU."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import runpy
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HELPER_PATH = REPO / "scripts/benchmark_quality.py"
INITIAL_HELPER_HASH = hashlib.sha256(HELPER_PATH.read_bytes()).hexdigest()
HELPERS = runpy.run_path(str(HELPER_PATH))


class BasicLimits(ctypes.Structure):
    _fields_ = [
        ("process_time", ctypes.c_longlong),
        ("job_time", ctypes.c_longlong),
        ("flags", wintypes.DWORD),
        ("min_working_set", ctypes.c_size_t),
        ("max_working_set", ctypes.c_size_t),
        ("active_processes", wintypes.DWORD),
        ("affinity", ctypes.c_size_t),
        ("priority", wintypes.DWORD),
        ("scheduling", wintypes.DWORD),
    ]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("basic", BasicLimits),
        ("io", ctypes.c_ulonglong * 6),
        ("process_memory", ctypes.c_size_t),
        ("job_memory", ctypes.c_size_t),
        ("peak_process_memory", ctypes.c_size_t),
        ("peak_job_memory", ctypes.c_size_t),
    ]


def windows_limits() -> tuple[ctypes.WinDLL, int, ExtendedLimits]:
    if os.name != "nt":
        raise RuntimeError("This qualification harness uses Windows job-object limits")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.GetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p]
    kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    process = kernel.GetCurrentProcess()
    allowed, system = ctypes.c_size_t(), ctypes.c_size_t()
    if not kernel.GetProcessAffinityMask(process, ctypes.byref(allowed), ctypes.byref(system)):
        raise ctypes.WinError(ctypes.get_last_error())
    limits = ExtendedLimits()
    limits.basic.flags = 0x100 | 0x10 | 0x2000  # PROCESS_MEMORY | AFFINITY | KILL_ON_JOB_CLOSE.
    limits.basic.affinity = allowed.value & -allowed.value
    limits.process_memory = 256 * 1024 * 1024
    job = kernel.CreateJobObjectW(None, None)
    if not job or not kernel.SetInformationJobObject(
        job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.AssignProcessToJobObject(job, process):
        raise ctypes.WinError(ctypes.get_last_error())
    observed = ctypes.c_size_t()
    if (
        not kernel.GetProcessAffinityMask(process, ctypes.byref(observed), ctypes.byref(system))
        or observed.value != limits.basic.affinity
    ):
        raise RuntimeError("One-CPU affinity was not applied")
    return kernel, job, limits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="Suppress unqualified timing")
    args = parser.parse_args()
    source, output = args.source_root.resolve(), args.output.resolve()
    if not args.worker:
        subprocess.run(
            [
                sys.executable,
                "-I",
                str(Path(__file__).resolve()),
                "--worker",
                "--source-root",
                str(source),
                "--output",
                str(output),
                *(["--smoke"] if args.smoke else []),
            ],
            env=HELPERS["controlled_environment"](),
            check=True,
            timeout=120,
        )
        return
    before = HELPERS["source_fingerprint"](source)
    initial_script = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    initial_environment = HELPERS["environment_metadata"](1)
    kernel, job, limits = windows_limits()
    started = time.perf_counter()
    sys.path.insert(0, str(source / "src"))
    import orqalis
    from orqalis.context.builder import ProjectContextBuilder
    from orqalis.graph.engine import ProjectGraphEngine
    from orqalis.sdk import Orqalis

    assert Path(orqalis.__file__).resolve().is_relative_to(source / "src")
    with tempfile.TemporaryDirectory(prefix="orqalis-constrained-") as temporary:
        root = Path(temporary)
        HELPERS["git"](root, "init", "-b", "main")
        for index in range(20):
            (root / f"service_{index}.py").write_text(
                f"def retry_offline_{index}(attempt):\n    return min(attempt, 5)\n",
                encoding="utf-8",
            )
        (root / "panel.tsx").write_text(
            "export const Panel = () => <main>offline retry</main>;", encoding="utf-8"
        )
        HELPERS["git"](root, "add", ".")
        HELPERS["git"](root, "commit", "-m", "constrained local fixture")
        sdk = Orqalis(root=root)
        sdk.initialize(root)
        graph = ProjectGraphEngine(root)
        assert graph.refresh().metrics.processed_files == 0
        contexts = []
        expected_paths = {f"service_{index}.py" for index in range(20)}
        for budget in (1000, 4000, 12000):
            pack = ProjectContextBuilder(root).build("retry offline attempt", max_chars=budget)
            text = pack.model_dump_json()
            contexts.append(
                {
                    "budget_chars": budget,
                    "serialized_chars": len(text),
                    "relevant_files": list(pack.relevant_files),
                    "matching_fixture_paths": sorted(
                        expected_paths.intersection(pack.relevant_files)
                    ),
                }
            )
            assert len(text) <= budget
            assert expected_paths.intersection(pack.relevant_files)
        sdk.close()
    elapsed_ms = (time.perf_counter() - started) * 1000
    if not kernel.QueryInformationJobObject(
        job, 9, ctypes.byref(limits), ctypes.sizeof(limits), None
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    assert limits.basic.flags & (0x100 | 0x10 | 0x2000) == (0x100 | 0x10 | 0x2000)
    assert limits.process_memory == 256 * 1024 * 1024
    assert limits.basic.affinity.bit_count() == 1
    assert 0 < limits.peak_process_memory <= limits.process_memory
    stable = (
        before == HELPERS["source_fingerprint"](source)
        and initial_script == hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        and hashlib.sha256(HELPER_PATH.read_bytes()).hexdigest() == INITIAL_HELPER_HASH
        and initial_environment == HELPERS["environment_metadata"](1)
    )
    report = {
        "schema_version": 1,
        "source_sha256": before["sha256"],
        "source_stable": stable,
        "script_sha256": initial_script,
        "helper_sha256": INITIAL_HELPER_HASH,
        "environment": initial_environment,
        "measurement_mode": "correctness-smoke" if args.smoke else "measurement",
        "status": "PASS" if stable else "FAIL",
        "cpu_affinity_mask": limits.basic.affinity,
        "cpu_count_allowed": 1,
        "process_commit_limit_bytes": limits.process_memory,
        "peak_process_commit_bytes": limits.peak_process_memory,
        "elapsed_ms": None if args.smoke else elapsed_ms,
        "contexts": contexts,
        "scope": (
            "Small local init/graph/context workload under enforced per-process commit cap; "
            "not whole-machine RAM, RSS, live-model or browser qualification"
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "status",
                    "cpu_count_allowed",
                    "process_commit_limit_bytes",
                    "peak_process_commit_bytes",
                    "elapsed_ms",
                )
            },
            indent=2,
        )
    )
    if not stable:
        raise RuntimeError("Source, harness or environment changed during constrained capture")


if __name__ == "__main__":
    main()
