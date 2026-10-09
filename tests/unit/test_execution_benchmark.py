"""Execution-harness evidence integrity checks without running the long workload."""

import argparse
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/benchmark_execution.py"
BENCH = runpy.run_path(str(SCRIPT))


def test_source_inventory_hashes_resources_and_ignores_bytecode(tmp_path: Path) -> None:
    package = tmp_path / "src/orqalis"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "policy.md").write_text("original policy")
    before = BENCH["source_fingerprint"](tmp_path)
    (package / "__pycache__").mkdir()
    (package / "__pycache__/runtime.pyc").write_bytes(b"derived")
    assert BENCH["source_fingerprint"](tmp_path) == before
    (package / "policy.md").write_text("changed policy")
    assert BENCH["source_fingerprint"](tmp_path)["sha256"] != before["sha256"]


def test_helper_bundle_is_frozen_and_content_addressed(tmp_path: Path) -> None:
    original, frozen = tmp_path / "original", tmp_path / "frozen"
    for relative in BENCH["HELPER_PATHS"]:
        target = original / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# fixture " + relative)
    identity = BENCH["freeze_helpers"](original, frozen)
    (original / "tests/support/trace_fixture.py").write_text("# changed after freeze")
    assert BENCH["fingerprint"](frozen, BENCH["HELPER_PATHS"]) == identity
    assert BENCH["fingerprint"](original, BENCH["HELPER_PATHS"]) != identity


def module(path: Path) -> ModuleType:
    result = ModuleType("fixture")
    result.__file__ = str(path)
    return result


def test_import_audit_rejects_mixed_checkout_modules(tmp_path: Path) -> None:
    source, helpers = tmp_path / "baseline", tmp_path / "helpers"
    modules = {
        "orqalis": module(source / "src/orqalis/__init__.py"),
        "tests.support.trace_fixture": module(helpers / "tests/support/trace_fixture.py"),
    }
    assert BENCH["verify_imports"](source, helpers, modules)
    modules["orqalis.execution.worker"] = module(
        tmp_path / "current/src/orqalis/execution/worker.py"
    )
    with pytest.raises(RuntimeError, match="escaped"):
        BENCH["verify_imports"](source, helpers, modules)


def test_isolated_process_uses_selected_source_despite_pythonpath(tmp_path: Path) -> None:
    source, helpers, poison = tmp_path / "source", tmp_path / "helpers", tmp_path / "poison"
    for root, name in ((source / "src", "selected"), (poison, "wrong")):
        package = root / "orqalis"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(f"ORIGIN = {name!r}\n")
    for relative in BENCH["HELPER_PATHS"]:
        target = helpers / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("")
    code = (
        "import sys,runpy,json;from pathlib import Path;"
        "h=runpy.run_path(sys.argv[1]);s=Path(sys.argv[2]);f=Path(sys.argv[3]);"
        "sys.path[:0]=[str(s/'src'),str(f)];"
        "import orqalis;import tests.support.trace_fixture;"
        "h['verify_imports'](s,f);"
        "print(json.dumps({'isolated':bool(sys.flags.isolated),'origin':orqalis.ORIGIN}))"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, str(SCRIPT), str(source), str(helpers)],
        env={**os.environ, "PYTHONPATH": str(poison)},
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert json.loads(result.stdout) == {"isolated": True, "origin": "selected"}


def passing_outcome() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        {
            "state": "REVIEWING",
            "review_outcomes": ["FAIL", "PASS"],
            "acceptance_first_pass": False,
            "acceptance_final": ["PASS"],
            "repair_iterations": 1,
            "plan_completion_percent": 100,
            "max_parallel_tasks": 2,
            "model_calls": 9,
            "model_statuses": {"SUCCEEDED": 9},
            "tool_calls": 2,
            "tool_statuses": {"SUCCEEDED": 2},
            "blocker_count": 0,
        },
        {
            "invocation_accounting": {"checks": dict.fromkeys(BENCH["ACCOUNTING_CHECKS"], True)},
            "persisted_reload_matches": True,
            "contiguous_events": True,
            "unique_event_keys": True,
            "event_cursor_matches": True,
            "worktree_answer": "answer = 43\n",
            "original_answer": "answer = 42\n",
        },
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("review_outcomes", ["FAIL", "FAIL"]),
        ("tool_calls", 1),
        ("model_statuses", {"FAILED": 9}),
        ("model_calls", 1),
        ("acceptance_first_pass", True),
    ],
)
def test_failed_execution_facts_never_become_success(field: str, value: Any) -> None:
    outcome, facts = passing_outcome()
    assert all(BENCH["checks_for"](outcome, facts).values())
    outcome[field] = value
    assert not all(BENCH["checks_for"](outcome, facts).values())


def test_persisted_state_and_original_source_are_required() -> None:
    outcome, facts = passing_outcome()
    for key in (
        "persisted_reload_matches",
        "contiguous_events",
        "unique_event_keys",
        "event_cursor_matches",
    ):
        changed = {**facts, key: False}
        assert not all(BENCH["checks_for"](outcome, changed).values())
    assert not all(BENCH["checks_for"](outcome, {**facts, "original_answer": "mutated"}).values())


def test_environment_scrubs_application_git_and_exporter_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ("ORQALIS_PROJECT_ROOT", "PYTHONPATH", "GIT_DIR", "OTEL_EXPORTER_OTLP_ENDPOINT"):
        monkeypatch.setenv(key, "fixture-sensitive-override")
    controlled = BENCH["controlled_environment"]()
    assert "fixture-sensitive-override" not in controlled.values()
    assert controlled["GIT_CONFIG_GLOBAL"] == os.devnull
    assert controlled["OTEL_SDK_DISABLED"] == "true"


def test_distribution_requires_measured_values() -> None:
    with pytest.raises(ValueError, match="actual samples"):
        BENCH["distribution"]([])
    observed = BENCH["distribution"]([10.0, 30.0, 20.0])
    assert observed["samples_ms"] == [10, 30, 20]
    assert observed["median_ms"] == 20 and observed["p95_ms"] == 30


def test_failed_worker_sample_remains_in_written_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, fixtures = tmp_path / "source", tmp_path / "fixtures"
    package = source / "src/orqalis"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    for relative in BENCH["HELPER_PATHS"]:
        target = fixtures / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# frozen stub")
    worker_environment = {"sha256": "f" * 64}
    monkeypatch.setitem(
        BENCH["capture"].__globals__, "environment_metadata", lambda: worker_environment
    )

    def failed_worker(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        output = Path(command[command.index("--output") + 1])
        helpers = Path(command[command.index("--fixture-root") + 1])
        outcome, _ = passing_outcome()
        sample = {
            "complete": True,
            "passed": False,
            "checks": {"fixture_outcome": False},
            "source_sha256": BENCH["source_fingerprint"](source)["sha256"],
            "helpers_sha256": BENCH["fingerprint"](helpers, BENCH["HELPER_PATHS"])["sha256"],
            "script_sha256": BENCH["sha256"](SCRIPT.read_bytes()),
            "environment_sha256": worker_environment["sha256"],
            "execution_elapsed_ms": 1.0,
            "outcome": outcome,
        }
        output.write_text(json.dumps(sample))
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(subprocess, "run", failed_worker)
    args = argparse.Namespace(
        source_root=source,
        fixture_root=fixtures,
        scratch_root=tmp_path / "scratch",
        output=tmp_path / "evidence.json",
        label="fixture",
        mode="smoke",
        repeat=1,
    )
    report = BENCH["capture"](args)
    assert report["complete"] and not report["passed"]
    assert report["summary"]["deterministic_fixture_passes"] == 0
    assert report["samples"][0]["worker_returncode"] == 1
    assert json.loads(args.output.read_text())["samples"][0]["checks"] == {"fixture_outcome": False}


def accounting_fixture() -> tuple[Any, ...]:
    run_id = uuid4()
    actors = tuple(
        SimpleNamespace(id=uuid4(), role=role)
        for role in ("architect", "developer", "repair", "reviewer")
    )
    providers = []
    events: list[SimpleNamespace] = []
    for actor, count in zip(actors, (2, 4, 1, 2), strict=True):
        for _ in range(count):
            providers.append(
                SimpleNamespace(
                    id=uuid4(),
                    run_id=run_id,
                    actor_session_id=actor.id,
                    task_execution_id=uuid4(),
                    provider="fixture",
                    model="deterministic-fixture",
                    status="SUCCEEDED",
                    started_at="started",
                    completed_at="completed",
                )
            )
    tools = tuple(
        SimpleNamespace(
            id=uuid4(),
            run_id=run_id,
            actor_session_id=provider.actor_session_id,
            task_execution_id=provider.task_execution_id,
            provider_invocation_id=provider.id,
            call_id="write-answer",
            tool="filesystem.write",
            status="SUCCEEDED",
            started_at="started",
            completed_at="completed",
        )
        for provider in (providers[2], providers[4])
    )
    for prefix, records, payload_field in (
        ("PROVIDER_INVOCATION", providers, "provider_execution_id"),
        ("TOOL", tools, "tool_invocation_id"),
    ):
        for record in records:
            for suffix, status, at in (
                ("STARTED", "RUNNING", "started"),
                ("COMPLETED", "SUCCEEDED", "completed"),
            ):
                events.append(
                    SimpleNamespace(
                        sequence=len(events) + 1,
                        event_type=f"{prefix}_{suffix}",
                        payload=SimpleNamespace(**{payload_field: record.id, "status": status}),
                        actor_session_id=record.actor_session_id,
                        task_execution_id=record.task_execution_id,
                        run_id=run_id,
                        occurred_at=at,
                    )
                )
    snapshot = SimpleNamespace(
        run=SimpleNamespace(id=run_id), providers=tuple(providers), tools=tools
    )
    return snapshot, tuple(providers), tools, actors, tuple(events)


def test_canonical_model_and_tool_records_have_exact_event_and_role_witnesses() -> None:
    evidence = BENCH["invocation_accounting"](*accounting_fixture())
    assert all(evidence["checks"].values())
    assert evidence["model_role_counts"] == {
        "architect": 2,
        "developer": 4,
        "repair": 1,
        "reviewer": 2,
    }
    assert len(evidence["provider"]["records"]) == 9
    assert len(evidence["tool"]["records"]) == 2


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_provider_record",
        "duplicate_provider_record",
        "missing_provider_projection",
        "duplicate_provider_projection",
        "missing_provider_start",
        "duplicate_provider_terminal",
        "foreign_provider_event",
        "wrong_provider_actor",
        "wrong_role_counts",
        "missing_tool_record",
        "duplicate_tool_record",
        "missing_tool_projection",
        "missing_tool_terminal",
        "duplicate_tool_start",
        "wrong_tool_status",
        "tool_terminal_before_start",
        "broken_tool_parent",
        "duplicate_actor",
    ],
)
def test_invocation_accounting_rejects_lost_or_duplicate_or_misbound_calls(mutation: str) -> None:
    snapshot, providers, tools, actors, events = accounting_fixture()
    if mutation == "missing_provider_record":
        providers = providers[1:]
    elif mutation == "duplicate_provider_record":
        providers = (*providers, providers[0])
    elif mutation == "missing_provider_projection":
        snapshot.providers = snapshot.providers[1:]
    elif mutation == "duplicate_provider_projection":
        snapshot.providers = (*snapshot.providers, snapshot.providers[0])
    elif mutation == "missing_provider_start":
        events = events[1:]
    elif mutation == "duplicate_provider_terminal":
        events = (*events, events[1])
    elif mutation == "foreign_provider_event":
        events[0].payload.provider_execution_id = uuid4()
    elif mutation == "wrong_provider_actor":
        events[0].actor_session_id = uuid4()
    elif mutation == "wrong_role_counts":
        actors[0].role = "developer"
    elif mutation == "missing_tool_record":
        tools = tools[1:]
    elif mutation == "duplicate_tool_record":
        tools = (*tools, tools[0])
    elif mutation == "missing_tool_projection":
        snapshot.tools = snapshot.tools[1:]
    elif mutation == "missing_tool_terminal":
        events = events[:-1]
    elif mutation == "duplicate_tool_start":
        events = (*events, events[-2])
    elif mutation == "wrong_tool_status":
        events[-1].payload.status = "FAILED"
    elif mutation == "tool_terminal_before_start":
        events[-1].sequence = 0
    elif mutation == "broken_tool_parent":
        tools[0].provider_invocation_id = uuid4()
    else:
        actors = (*actors, actors[0])
    evidence = BENCH["invocation_accounting"](snapshot, providers, tools, actors, events)
    assert not all(evidence["checks"].values())
    outcome, facts = passing_outcome()
    facts["invocation_accounting"] = evidence
    assert not all(BENCH["checks_for"](outcome, facts).values())


def test_missing_accounting_check_and_single_model_record_cannot_pass() -> None:
    outcome, facts = passing_outcome()
    outcome.update(model_calls=1, model_statuses={"SUCCEEDED": 1})
    assert not all(BENCH["checks_for"](outcome, facts).values())
    outcome, facts = passing_outcome()
    del facts["invocation_accounting"]["checks"]["provider_events_match"]
    assert not all(BENCH["checks_for"](outcome, facts).values())
