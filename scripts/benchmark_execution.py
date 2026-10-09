"""Source-isolated deterministic execution measurements, separate from retrieval quality.

The frozen fake-provider fixture exercises parallel reads, persisted tools, failed
acceptance, one repair and a passing review. It stops before delivery. These are
orchestration measurements, not live-model coding success, token or cost estimates.
Use identical helper and environment hashes for baseline/current comparisons.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

REPO = Path(__file__).resolve().parents[1]
HELPER_PATHS = (
    "tests/__init__.py",
    "tests/support/filesystem.py",
    "tests/support/trace_fixture.py",
)
FIXTURE_FILES = {
    "pyproject.toml": '[project]\nname = "fixture"\n',
    "main.py": "answer = 42\n",
    "AGENTS.md": "Run tests before delivery.\n",
    "tests/test_main.py": "def test_answer():\n    assert 42 == 42\n",
}
CASE_ID = "parallel-read-one-repair-reviewed-execution-v1"
ENVIRONMENT_POLICY = "execution-v1; isolated Python; scrub application overrides; isolated Git"
EXPECTED_MODEL_ROLES = {"architect": 2, "developer": 4, "repair": 1, "reviewer": 2}
ACCOUNTING_CHECKS = (
    "provider_ids_unique",
    "provider_projection_matches",
    "provider_events_match",
    "tool_ids_unique",
    "tool_projection_matches",
    "tool_events_match",
    "actor_ids_unique",
    "model_role_counts_match",
    "tool_role_counts_match",
    "tool_provider_links_match",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def fingerprint(root: Path, paths: list[str] | tuple[str, ...]) -> dict[str, Any]:
    digest = hashlib.sha256()
    files = []
    for relative in sorted(paths):
        content = (root / relative).read_bytes()
        digest.update(relative.encode() + b"\0" + content + b"\0")
        files.append({"path": relative, "sha256": sha256(content), "bytes": len(content)})
    return {"sha256": digest.hexdigest(), "files": files}


def source_fingerprint(root: Path) -> dict[str, Any]:
    if not (root / "src/orqalis/__init__.py").is_file():
        raise ValueError("--source-root must contain src/orqalis")
    paths = [
        path.relative_to(root).as_posix()
        for path in (root / "src/orqalis").rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    ]
    paths.extend(name for name in ("pyproject.toml", "uv.lock") if (root / name).is_file())
    return fingerprint(root, paths)


def controlled_environment() -> dict[str, str]:
    result = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("ORQALIS_", "PYTHON", "PYTEST", "GIT_", "OTEL_"))
    }
    result.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_NO_REPLACE_OBJECTS="1",
        GIT_AUTHOR_DATE="2020-01-01T00:00:00+0000",
        GIT_COMMITTER_DATE="2020-01-01T00:00:00+0000",
        OTEL_SDK_DISABLED="true",
        LC_ALL="C",
        TZ="UTC",
    )
    return result


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.autocrlf=false",
            "-c",
            "user.name=Execution Fixture",
            "-c",
            "user.email=execution@orqalis.invalid",
            "-C",
            str(root),
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
        env=controlled_environment(),
    ).stdout.strip()


def environment_metadata() -> dict[str, Any]:
    dependencies = sorted(
        {
            (d.metadata.get("Name", "").lower(), d.version)
            for d in importlib.metadata.distributions()
        }
    )
    value = {
        "python": sys.version,
        "executable_sha256": sha256(Path(sys.executable).read_bytes()),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "git_version": git(REPO, "--version"),
        "isolated_python": bool(sys.flags.isolated),
        "dependencies": dependencies,
        "policy": ENVIRONMENT_POLICY,
    }
    return {**value, "sha256": canonical_hash(value)}


def freeze_helpers(root: Path, destination: Path) -> dict[str, Any]:
    before = fingerprint(root, HELPER_PATHS)
    for relative in HELPER_PATHS:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, target)
    if fingerprint(destination, HELPER_PATHS) != before:
        raise RuntimeError("Fixture helper changed while freezing")
    return before


def verify_imports(
    source: Path, helpers: Path, modules: Mapping[str, ModuleType] | None = None
) -> dict[str, str]:
    """Reject any package/helper module imported from a different checkout or installation."""
    locations = {}
    for name, module in (sys.modules if modules is None else modules).items():
        if name == "orqalis" or name.startswith("orqalis."):
            expected = source / "src"
        elif name == "tests" or name.startswith("tests."):
            expected = helpers
        else:
            continue
        filename = getattr(module, "__file__", None)
        if filename:
            path = Path(filename).resolve()
            if not path.is_relative_to(expected.resolve()):
                raise RuntimeError(f"Import escaped selected source/helper root: {name}")
            locations[name] = path.relative_to(expected.resolve()).as_posix()
        else:
            for entry in getattr(module, "__path__", ()):
                if not Path(entry).resolve().is_relative_to(expected.resolve()):
                    raise RuntimeError(f"Namespace escaped selected helper root: {name}")
    if "orqalis" not in locations or "tests.support.trace_fixture" not in locations:
        raise RuntimeError("Expected selected source and frozen execution fixture were not loaded")
    return dict(sorted(locations.items()))


def execution_outcome(snapshot: Any) -> dict[str, Any]:
    reviews = [item.result.overall for item in snapshot.reviews]
    first_criteria = snapshot.reviews[0].result.criteria if snapshot.reviews else ()
    return {
        "run_id": str(snapshot.run.id),
        "state": str(snapshot.run.state),
        "review_outcomes": reviews,
        "acceptance_first_pass": all(item.status == "PASS" for item in first_criteria)
        if first_criteria
        else None,
        "review_first_pass": reviews[0] == "PASS" if reviews else None,
        "acceptance_final": [item.status for item in snapshot.goal.criteria]
        if snapshot.goal
        else [],
        "repair_iterations": snapshot.run.repair_iteration,
        "plan_version": snapshot.run.plan_version,
        "plan_completion_percent": snapshot.plan_completion,
        "model_calls": len(snapshot.providers),
        "model_statuses": dict(Counter(str(item.status) for item in snapshot.providers)),
        "tool_calls": len(snapshot.tools),
        "tool_statuses": dict(Counter(str(item.status) for item in snapshot.tools)),
        "max_parallel_tasks": snapshot.statistics.max_parallel_tasks,
        "event_sequence": snapshot.last_event_sequence,
        "blocker_count": len(snapshot.blockers),
    }


def invocation_accounting(
    snapshot: Any,
    providers: tuple[Any, ...],
    tools: tuple[Any, ...],
    actors: tuple[Any, ...],
    events: tuple[Any, ...],
) -> dict[str, Any]:
    """Join persisted records, projections and lifecycle events; never infer saved calls."""
    roles = {str(actor.id): str(actor.role) for actor in actors}
    checks = {"actor_ids_unique": len(roles) == len(actors)}
    evidence: dict[str, Any] = {}
    for kind, records, projections, event_prefix, payload_key, fields in (
        (
            "provider",
            providers,
            snapshot.providers,
            "PROVIDER_INVOCATION",
            "provider_execution_id",
            ("actor_session_id", "task_execution_id", "provider", "model"),
        ),
        (
            "tool",
            tools,
            snapshot.tools,
            "TOOL",
            "tool_invocation_id",
            ("actor_session_id", "task_execution_id", "provider_invocation_id", "call_id", "tool"),
        ),
    ):
        by_id = {str(item.id): item for item in records}
        projected = {str(item.id): item for item in projections}
        checks[f"{kind}_ids_unique"] = len(by_id) == len(records) and len(projected) == len(
            projections
        )
        checks[f"{kind}_projection_matches"] = set(by_id) == set(projected) and all(
            all(
                getattr(record, field) == getattr(projected[key], field)
                for field in (*fields, "status", "started_at", "completed_at")
            )
            for key, record in by_id.items()
        )
        starts = [event for event in events if str(event.event_type) == f"{event_prefix}_STARTED"]
        terminals = [
            event for event in events if str(event.event_type) == f"{event_prefix}_COMPLETED"
        ]
        start_ids = [str(getattr(event.payload, payload_key)) for event in starts]
        terminal_ids = [str(getattr(event.payload, payload_key)) for event in terminals]
        event_match = Counter(start_ids) == Counter({key: 1 for key in by_id}) and Counter(
            terminal_ids
        ) == Counter({key: 1 for key in by_id})
        rows = []
        for key, record in by_id.items():
            start = next(
                (event for event in starts if str(getattr(event.payload, payload_key)) == key), None
            )
            terminal = next(
                (event for event in terminals if str(getattr(event.payload, payload_key)) == key),
                None,
            )
            matches = start is not None and terminal is not None
            if start is not None and terminal is not None:
                matches = (
                    start.sequence < terminal.sequence
                    and start.payload.status == "RUNNING"
                    and terminal.payload.status == record.status == "SUCCEEDED"
                    and start.occurred_at == record.started_at
                    and terminal.occurred_at == record.completed_at
                    and start.actor_session_id
                    == terminal.actor_session_id
                    == record.actor_session_id
                    and start.task_execution_id
                    == terminal.task_execution_id
                    == record.task_execution_id
                    and start.run_id == terminal.run_id == record.run_id == snapshot.run.id
                )
            event_match = event_match and matches
            rows.append(
                {
                    "id": key,
                    "actor_session_id": str(record.actor_session_id),
                    "task_execution_id": str(record.task_execution_id),
                    "role": roles.get(str(record.actor_session_id)),
                    "status": str(record.status),
                    "start_sequence": start.sequence if start is not None else None,
                    "terminal_sequence": terminal.sequence if terminal is not None else None,
                    "record_and_events_match": matches,
                }
            )
        checks[f"{kind}_events_match"] = event_match
        evidence[kind] = {
            "records": rows,
            "projection_ids": [str(item.id) for item in projections],
            "start_event_ids": start_ids,
            "terminal_event_ids": terminal_ids,
        }
    model_roles = dict(
        Counter(roles.get(str(item.actor_session_id), "UNKNOWN") for item in providers)
    )
    tool_roles = dict(Counter(roles.get(str(item.actor_session_id), "UNKNOWN") for item in tools))
    checks["model_role_counts_match"] = model_roles == EXPECTED_MODEL_ROLES
    checks["tool_role_counts_match"] = tool_roles == {"developer": 2} and Counter(
        str(item.tool) for item in tools
    ) == {"filesystem.write": 2}
    provider_by_id = {item.id: item for item in providers}
    checks["tool_provider_links_match"] = (
        all(
            item.provider_invocation_id in provider_by_id
            and provider_by_id[item.provider_invocation_id].actor_session_id
            == item.actor_session_id
            and provider_by_id[item.provider_invocation_id].task_execution_id
            == item.task_execution_id
            for item in tools
        )
        and len({item.provider_invocation_id for item in tools}) == 2
    )
    return {
        "checks": checks,
        "model_role_counts": model_roles,
        "expected_model_role_counts": EXPECTED_MODEL_ROLES,
        "tool_role_counts": tool_roles,
        **evidence,
    }


def checks_for(outcome: dict[str, Any], facts: dict[str, Any]) -> dict[str, bool]:
    return {
        "reviewed_execution_checkpoint": outcome["state"] == "REVIEWING",
        "failed_first_review_then_pass": outcome["review_outcomes"] == ["FAIL", "PASS"],
        "deliberate_first_acceptance_failure": outcome["acceptance_first_pass"] is False,
        "final_acceptance_pass": outcome["acceptance_final"] == ["PASS"],
        "exactly_one_repair": outcome["repair_iterations"] == 1,
        "current_plan_complete": outcome["plan_completion_percent"] == 100,
        "parallel_read_tasks_observed": outcome["max_parallel_tasks"] == 2,
        "all_model_calls_succeeded": outcome["model_calls"] == sum(EXPECTED_MODEL_ROLES.values())
        and outcome["model_statuses"] == {"SUCCEEDED": outcome["model_calls"]},
        "exactly_two_successful_writes": outcome["tool_calls"] == 2
        and outcome["tool_statuses"] == {"SUCCEEDED": 2},
        "no_blockers": outcome["blocker_count"] == 0,
        **{
            name: facts["invocation_accounting"]["checks"].get(name) is True
            for name in ACCOUNTING_CHECKS
        },
        "persisted_reload_matches": facts["persisted_reload_matches"],
        "contiguous_events": facts["contiguous_events"],
        "unique_event_keys": facts["unique_event_keys"],
        "event_cursor_matches": facts["event_cursor_matches"],
        "worktree_answer_correct": facts["worktree_answer"] == "answer = 43\n",
        "original_source_unchanged": facts["original_answer"] == "answer = 42\n",
    }


def worker(args: argparse.Namespace) -> dict[str, Any]:
    if not sys.flags.isolated:
        raise RuntimeError("Execution workers require Python -I")
    source_before = source_fingerprint(args.source_root)
    helpers_before = fingerprint(args.fixture_root, HELPER_PATHS)
    script_before = sha256(Path(__file__).read_bytes())
    environment_before = environment_metadata()
    if any(name == "orqalis" or name.startswith("orqalis.") for name in sys.modules):
        raise RuntimeError("Orqalis imported before selecting the measured source")
    sys.path[:0] = [str(args.source_root / "src"), str(args.fixture_root)]
    from orqalis.persistence.filesystem import TaskCapsuleStore
    from orqalis.sdk import Orqalis
    from tests.support.filesystem import filesystem_uow_factory
    from tests.support.trace_fixture import execute_trace_fixture

    verify_imports(args.source_root, args.fixture_root)
    repository = args.workspace / "repository"
    repository.mkdir(parents=True)
    setup_started = time.perf_counter()
    for relative, content in FIXTURE_FILES.items():
        target = repository / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode())
    git(repository, "init", "-b", "main")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "benchmark: frozen execution fixture")
    fixture_commit = git(repository, "rev-parse", "HEAD")
    setup_ms = (time.perf_counter() - setup_started) * 1000
    started = time.perf_counter()
    snapshot = asyncio.run(execute_trace_fixture(repository, args.workspace / "workers"))
    execution_ms = (time.perf_counter() - started) * 1000
    outcome = execution_outcome(snapshot)
    sdk = Orqalis(unit_of_work=filesystem_uow_factory(repository))
    try:
        reopened = sdk.snapshot(snapshot.run.id)
        with filesystem_uow_factory(repository)() as uow:
            events = uow.events.list(snapshot.run.id)
            invocation_evidence = invocation_accounting(
                snapshot,
                uow.providers.list(snapshot.run.id),
                uow.execution.tools(snapshot.run.id),
                uow.runtime.actors(snapshot.run.id),
                events,
            )
            binding = uow.execution.workspace(snapshot.run.id)
            if binding is None:
                raise RuntimeError("Execution fixture did not persist a workspace binding")
        facts = {
            "invocation_accounting": invocation_evidence,
            "persisted_reload_matches": execution_outcome(reopened) == outcome,
            "contiguous_events": [e.sequence for e in events] == list(range(1, len(events) + 1)),
            "unique_event_keys": len({e.idempotency_key for e in events}) == len(events),
            "event_cursor_matches": snapshot.last_event_sequence == len(events),
            "worktree_answer": (binding.path / "main.py").read_text(encoding="utf-8"),
            "original_answer": (repository / "main.py").read_text(encoding="utf-8"),
        }
        capsule = TaskCapsuleStore.from_root(repository).capsule_path(snapshot.run.id)
        if capsule is None:
            raise RuntimeError("Execution fixture has no durable capsule")
        persisted = fingerprint(capsule, ["execution/state.yaml", "execution/events.jsonl"])
    finally:
        sdk.close()
    checks = checks_for(outcome, facts)
    stability = {
        "source": source_before == source_fingerprint(args.source_root),
        "helpers": helpers_before == fingerprint(args.fixture_root, HELPER_PATHS),
        "script": script_before == sha256(Path(__file__).read_bytes()),
        "environment": environment_before == environment_metadata(),
    }
    return {
        "complete": True,
        "passed": all(checks.values()) and all(stability.values()),
        "checks": checks,
        "input_stability": stability,
        "source_sha256": source_before["sha256"],
        "helpers_sha256": helpers_before["sha256"],
        "script_sha256": script_before,
        "environment_sha256": environment_before["sha256"],
        "isolated_python": True,
        "loaded_modules": verify_imports(args.source_root, args.fixture_root),
        "fixture_commit": fixture_commit,
        "outcome": outcome,
        "persisted": persisted,
        "event_type_counts": dict(Counter(str(event.event_type) for event in events)),
        "invocation_accounting": invocation_evidence,
        "model_invocation_ids": [str(item.id) for item in snapshot.providers],
        "tool_invocation_ids": [str(item.id) for item in snapshot.tools],
        "execution_elapsed_ms": execution_ms,
        "repository_setup_elapsed_ms": setup_ms,
        "persisted_run_timing_ms": snapshot.timing.model_dump(mode="json"),
        "timing_observed_at": snapshot.server_time.isoformat(),
        "reported_usage": {
            name: getattr(snapshot.statistics, name, None)
            for name in (
                "calls_with_usage",
                "calls_with_cost",
                "reported_input_tokens",
                "reported_output_tokens",
                "reported_cached_tokens",
                "reported_cost_usd",
            )
        },
    }


def distribution(samples: list[float]) -> dict[str, Any]:
    if not samples:
        raise ValueError("A distribution requires actual samples")
    return {
        "samples_ms": samples,
        "median_ms": statistics.median(samples),
        "p95_ms": sorted(samples)[math.ceil(len(samples) * 0.95) - 1],
        "p95_method": "nearest-rank; small-sample maximum is not a tail-latency estimate",
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def capture(args: argparse.Namespace) -> dict[str, Any]:
    source = source_fingerprint(args.source_root)
    helpers = fingerprint(args.fixture_root, HELPER_PATHS)
    script_hash = sha256(Path(__file__).read_bytes())
    environment = environment_metadata()
    report: dict[str, Any] = {
        "schema_version": 1,
        "case_id": CASE_ID,
        "label": args.label,
        "mode": args.mode,
        "captured_at": datetime.now(UTC).isoformat(),
        "source_root": str(args.source_root),
        "source": source,
        "helpers": helpers,
        "script_sha256": script_hash,
        "fixture_sha256": canonical_hash(FIXTURE_FILES),
        "environment": environment,
        "repetitions": args.repeat,
        "provider_mode": "injected deterministic fake; no live model calls",
        "completion_boundary": "persisted passing review; no documentation, Git delivery or push",
        "measurement_scope": "fresh repository; fixture initialization through passing review",
        "limitations": [
            "One deliberately repair-requiring fixture; not autonomous "
            "coding quality or general task success.",
            "First-pass acceptance is expected false by fixture design, "
            "not a model accuracy score.",
            "Event-projected active/waiting time is not CPU time; "
            "concurrent task times are not summed.",
            "Fake provider reports no usage/cost; null fields remain "
            "unavailable, not zero or estimated.",
            "Interpreter startup/Git fixture setup/reload checks are "
            "excluded from execution_elapsed_ms.",
            "Smoke timings are unqualified; capture mode requires an "
            "externally coordinated quiet environment.",
        ],
        "samples": [],
        "complete": False,
    }
    write_report(args.output, report)
    args.scratch_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="execution-benchmark-", dir=args.scratch_root
    ) as directory:
        scratch = Path(directory).resolve()
        if scratch.parent != args.scratch_root:
            raise RuntimeError("Temporary workspace escaped the explicit scratch root")
        frozen = scratch / "helpers"
        if freeze_helpers(args.fixture_root, frozen) != helpers:
            raise RuntimeError("Fixture helper changed before the run")
        for repetition in range(args.repeat):
            result_path = scratch / f"sample-{repetition}.json"
            command = [
                sys.executable,
                "-I",
                str(Path(__file__).resolve()),
                "--worker",
                "--source-root",
                str(args.source_root),
                "--fixture-root",
                str(frozen),
                "--output",
                str(result_path),
                "--workspace",
                str(scratch / f"run-{repetition}"),
            ]
            started = time.perf_counter()
            completed = subprocess.run(
                command, env=controlled_environment(), check=False, timeout=300
            )
            if not result_path.is_file():
                report["failure"] = {
                    "repetition": repetition,
                    "worker_returncode": completed.returncode,
                }
                write_report(args.output, report)
                raise RuntimeError("Isolated execution worker failed; evidence remains incomplete")
            sample = json.loads(result_path.read_text(encoding="utf-8"))
            sample["child_process_elapsed_ms"] = (time.perf_counter() - started) * 1000
            sample["repetition"] = repetition
            sample["worker_returncode"] = completed.returncode
            if completed.returncode not in {0, 1} or bool(sample["passed"]) != (
                completed.returncode == 0
            ):
                raise RuntimeError("Worker exit status disagrees with its reported outcome")
            if (
                sample["source_sha256"] != source["sha256"]
                or sample["helpers_sha256"] != helpers["sha256"]
                or sample["script_sha256"] != script_hash
                or sample["environment_sha256"] != environment["sha256"]
            ):
                raise RuntimeError("Worker inputs differ from the frozen parent report")
            report["samples"].append(sample)
            write_report(args.output, report)
    stable = (
        source == source_fingerprint(args.source_root)
        and helpers == fingerprint(args.fixture_root, HELPER_PATHS)
        and script_hash == sha256(Path(__file__).read_bytes())
        and environment == environment_metadata()
    )
    report["input_stable"] = stable
    report["complete"] = True
    report["passed"] = stable and all(row["passed"] for row in report["samples"])
    report["summary"] = {
        "deterministic_fixture_passes": sum(row["passed"] for row in report["samples"]),
        "acceptance_first_pass_count": sum(
            row["outcome"]["acceptance_first_pass"] is True for row in report["samples"]
        ),
        "timing_qualified": args.mode == "capture" and report["passed"],
        "execution_elapsed": distribution(
            [row["execution_elapsed_ms"] for row in report["samples"]]
        ),
        "child_process_elapsed": distribution(
            [row["child_process_elapsed_ms"] for row in report["samples"]]
        ),
    }
    write_report(args.output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--fixture-root", type=Path, default=REPO)
    parser.add_argument("--scratch-root", type=Path, default=REPO / ".tools/research")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", default="current")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--mode", choices=("smoke", "capture"), default="smoke")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--workspace", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.repeat <= 10:
        parser.error("--repeat must be 1..10")
    for name in ("source_root", "fixture_root", "scratch_root", "output", "workspace"):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, value.resolve())
    if not sys.flags.isolated:
        raise SystemExit(
            subprocess.run(
                [sys.executable, "-I", str(Path(__file__).resolve()), *sys.argv[1:]],
                env=controlled_environment(),
                check=False,
            ).returncode
        )
    if args.worker:
        if args.workspace is None:
            parser.error("Worker requires an explicit disposable workspace")
        report = worker(args)
        write_report(args.output, report)
    else:
        report = capture(args)
        print(
            json.dumps({"output": str(args.output), "passed": report["passed"], "mode": args.mode})
        )
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
