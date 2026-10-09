"""Run frozen deterministic contract tests against an explicitly selected Orqalis source.

Use the same --tests-root for baseline/current. JUnit counts are contract evidence,
not live-model task success. This runner never invokes the benchmark workload.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

HELPER_PATH = Path(__file__).with_name("benchmark_quality.py")
HELPER_BYTES = HELPER_PATH.read_bytes()
HELPER_SHA256 = hashlib.sha256(HELPER_BYTES).hexdigest()
HELPERS: dict[str, Any] = {"__file__": str(HELPER_PATH), "__name__": "_quality_contract_helpers"}
exec(compile(HELPER_BYTES, str(HELPER_PATH), "exec"), HELPERS)


def test_fingerprint(root: Path) -> str:
    files = sorted(
        p.relative_to(root).as_posix()
        for p in (root / "tests").rglob("*.py")
        if "__pycache__" not in p.parts
    )
    if (root / "pyproject.toml").is_file():
        files.append("pyproject.toml")
    return cast(str, HELPERS["digest_files"](root, files))


def install_child_source_guard(source: Path, audit_path: Path) -> None:
    """Bind known Orqalis child launch forms without changing approved workspace commands."""
    launch = (
        "import sys,runpy;from pathlib import Path;source=Path(sys.argv.pop(1));"
        "sys.path.insert(0,str(source/'src'));import orqalis;"
        "assert Path(orqalis.__file__).resolve().is_relative_to(source/'src');"
        "runpy.run_module('orqalis',run_name='__main__')"
    )

    def source_bound_command(command: Any, options: dict[str, Any]) -> Any:
        if not isinstance(command, (list, tuple)) or not command:
            return command
        argv = [str(value) for value in command]
        name = Path(argv[0]).name.lower()
        tail = None
        if name in {"orqalis", "orqalis.exe", "orqalis.cmd", "orqalis.bat"}:
            tail = argv[1:]
        elif Path(argv[0]).resolve() == Path(sys.executable).resolve():
            if argv[1:3] == ["-m", "orqalis"]:
                tail = argv[3:]
            elif argv[1:4] == ["-I", "-m", "orqalis"]:
                tail = argv[4:]
        if tail is None:
            return command
        if options.get("shell") or options.get("executable"):
            raise ValueError("Unsupported Orqalis child launch override")
        with audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"launcher": name, "selected_source": str(source)}) + "\n")
        return [sys.executable, "-I", "-c", launch, str(source), *tail]

    class SourceBoundPopen(subprocess.Popen[Any]):
        def __init__(self, command: Any, *args: Any, **kwargs: Any) -> None:
            super().__init__(source_bound_command(command, kwargs), *args, **kwargs)

    original_subprocess_exec = asyncio.BaseEventLoop.subprocess_exec

    async def source_bound_subprocess_exec(
        loop: asyncio.BaseEventLoop,
        protocol_factory: Any,
        program: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        # AnyIO calls the loop directly. Windows' overlapped-pipe Popen subclass
        # retains its original superclass and bypasses subprocess.Popen overrides.
        # Rewrite argv before transport creation and preserve its native cleanup.
        command = source_bound_command([program, *args], kwargs)
        return await original_subprocess_exec(loop, protocol_factory, *command, **kwargs)

    subprocess.__dict__["Popen"] = SourceBoundPopen
    asyncio.BaseEventLoop.subprocess_exec = cast(Any, source_bound_subprocess_exec)  # type: ignore[method-assign]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--tests-root", type=Path, required=True)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "benchmarks/engineering_cases.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    for name in ("source_root", "tests_root", "dataset", "output"):
        setattr(args, name, getattr(args, name).resolve())
    if not args.worker:
        command = [
            sys.executable,
            "-I",
            str(Path(__file__).resolve()),
            "--worker",
            "--source-root",
            str(args.source_root),
            "--tests-root",
            str(args.tests_root),
            "--dataset",
            str(args.dataset),
            "--output",
            str(args.output),
        ]
        raise SystemExit(
            subprocess.run(command, env=HELPERS["controlled_environment"](), check=False).returncode
        )
    dataset_bytes = args.dataset.read_bytes()
    dataset = json.loads(dataset_bytes)
    HELPERS["validate_dataset"](dataset)
    paths = sorted({path for case in dataset["cases"] for path in case["contract_tests"]})
    if any(not (args.tests_root / path).is_file() for path in paths):
        raise ValueError("Frozen contract test checkout lacks a dataset test file")
    before = HELPERS["source_fingerprint"](args.source_root)
    tests_before = test_fingerprint(args.tests_root)
    script_before = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    junit = args.output.with_suffix(".junit.xml")
    child_audit = args.output.with_suffix(".children.jsonl")
    child_audit.write_text("", encoding="utf-8")
    bootstrap = (
        "import sys,runpy;from pathlib import Path;"
        "source=Path(sys.argv.pop(1));tests=Path(sys.argv.pop(1));"
        "runner=sys.argv.pop(1);audit=Path(sys.argv.pop(1));"
        "runpy.run_path(runner)['install_child_source_guard'](source,audit);"
        "sys.path[:0]=[str(source/'src'),str(tests)];"
        "import orqalis;assert Path(orqalis.__file__).resolve().is_relative_to(source/'src');"
        "import pytest;raise SystemExit(pytest.main(sys.argv[1:]))"
    )
    command = [
        sys.executable,
        "-I",
        "-c",
        bootstrap,
        str(args.source_root),
        str(args.tests_root),
        str(Path(__file__).resolve()),
        str(child_audit),
        "-q",
        "-o",
        "addopts=",
        "--rootdir",
        str(args.tests_root),
        "--confcutdir",
        str(args.tests_root),
        "--junitxml",
        str(junit),
        *(str(args.tests_root / path) for path in paths),
    ]
    result = subprocess.run(
        command, cwd=args.tests_root, env=HELPERS["controlled_environment"](), check=False
    )
    report = {
        "schema_version": 2,
        "source_sha256": before["sha256"],
        "source_stable": before == HELPERS["source_fingerprint"](args.source_root),
        "tests_sha256": tests_before,
        "tests_stable": tests_before == test_fingerprint(args.tests_root),
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "runner_sha256": script_before,
        "runner_stable": hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == script_before,
        "helper_sha256": HELPER_SHA256,
        "helper_stable": hashlib.sha256(HELPER_PATH.read_bytes()).hexdigest() == HELPER_SHA256,
        "dataset_stable": args.dataset.read_bytes() == dataset_bytes,
        "environment": HELPERS["environment_metadata"](1),
        "exit_code": result.returncode,
        "child_source_policy": "rewrite-known-orqalis-cli-and-python-module-v2",
        "child_launches": [
            json.loads(line) for line in child_audit.read_text(encoding="utf-8").splitlines()
        ],
        "launcher_scope": (
            "Contract CLI children use selected source; installed entrypoint/package "
            "itself is not qualified by this runner."
        ),
        "junit": HELPERS["contract_junit"](junit, paths),
        "live_engineering_task_success": None,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "junit": report["junit"]}, indent=2))
    if (
        result.returncode
        or not report["source_stable"]
        or not report["tests_stable"]
        or not report["runner_stable"]
        or not report["helper_stable"]
        or not report["dataset_stable"]
        or not report["junit"]["passed"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
