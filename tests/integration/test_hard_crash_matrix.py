import json
import os
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock
from uuid import UUID

import pytest

from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.errors import ConflictError
from orqalis.persistence.filesystem import TaskCapsuleStore
from orqalis.persistence.filesystem.io import atomic_write_bytes
from orqalis.sdk import Orqalis
from tests.conftest import fixture_git
from tests.support.filesystem import filesystem_uow_factory


def _terminate_controller(process: subprocess.Popen[bytes], probe: Callable[[], bool]) -> None:
    assert process.poll() is None, "Controller exited before its crash barrier"
    assert not probe(), "Live controller failed to exclude a competing lease"
    # Windows may release byte locks after process termination becomes observable.
    # Process wait and lease release share the existing termination budget.
    deadline = time.monotonic() + 30
    process.kill()
    process.wait(timeout=max(0.0, deadline - time.monotonic()))
    while True:
        assert time.monotonic() < deadline, "Dead controller lease exceeded termination budget"
        acquired = probe()  # Fresh UoW; a successful probe closes before returning.
        observed_at = time.monotonic()
        assert observed_at <= deadline, "Dead controller lease exceeded termination budget"
        if acquired:
            return
        remaining = deadline - observed_at
        assert remaining > 0, "Dead controller retained its lease"
        time.sleep(min(0.02, remaining))


def _child(
    root: Path,
    worktrees: Path,
    run_id: UUID,
    phase: str,
    marker: Path,
    audit: Path,
) -> dict[str, Any]:
    log = marker.with_suffix(".stderr")
    factory = filesystem_uow_factory(root)

    def lease_probe() -> bool:
        with factory() as lease:
            return lease.execution.try_run_lock(run_id)

    with log.open("wb") as errors:
        process = subprocess.Popen(
            (
                sys.executable,
                "-m",
                "tests.support.crash_worker",
                str(root),
                str(worktrees),
                str(run_id),
                phase,
                str(marker),
                str(audit),
            ),
            stdout=subprocess.DEVNULL,
            stderr=errors,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        try:
            deadline = time.monotonic() + 180
            while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            assert marker.exists(), f"{phase} barrier missing: {log.read_text(errors='replace')}"
            if phase != "complete":
                _terminate_controller(process, lease_probe)
            else:
                process.wait(timeout=30)
                assert process.returncode == 0, log.read_text(errors="replace")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=30)
    result: dict[str, Any] = json.loads(marker.read_text())
    return result


def test_hard_kill_matrix_preserves_history_and_deduplicates_effects(
    git_repo: Path,
    tmp_path: Path,
) -> None:
    factory = filesystem_uow_factory(git_repo)
    sdk = Orqalis(unit_of_work=factory)
    project = sdk.initialize(git_repo)
    prepared = sdk.prepare_run(
        project.id,
        "Change answer",
        "feature/hard-kill-matrix",
        GoalDraft(
            goal="Change answer",
            scope=("main.py", "README.md"),
            definition_of_done=("Observed evidence and reviewed delivery",),
            criteria=(
                CriterionDefinition(
                    key="AC-1",
                    description="Answer is 43",
                    validation_spec=FileValidation(path="main.py", contains="answer = 43"),
                ),
            ),
        ),
    )
    run_id, worktrees = prepared.run.id, tmp_path / "workers"
    audit = tmp_path / "effects.jsonl"
    states = {
        "planning": "GOAL_DEFINED",
        "tool": "EXECUTING",
        "agent": "EXECUTING",
        "review": "REVIEWING",
        "repair": "REPAIR_PLANNING",
        "documentation": "DOCUMENTING",
        "git_prepare": "COMMITTING",
        "git_attach": "COMMITTING",
    }
    barriers = {}
    previous_events: tuple[object, ...] = ()
    for phase, state in states.items():
        barriers[phase] = _child(
            git_repo, worktrees, run_id, phase, tmp_path / f"{phase}.json", audit
        )
        snapshot = sdk.snapshot(run_id)
        assert snapshot.run.state == state
        with factory() as uow:
            events = uow.events.list(run_id)
            assert tuple(events[: len(previous_events)]) == previous_events
            assert [event.sequence for event in events] == list(range(1, len(events) + 1))
            assert len({event.idempotency_key for event in events}) == len(events)
            previous_events = events
        if phase == "planning":
            # Corrupted canonical snapshots fail visibly and are never silently rebuilt.
            capsule = TaskCapsuleStore.from_root(git_repo).capsule_path(run_id)
            assert capsule is not None
            state_path = capsule / "execution" / "state.yaml"
            contents = state_path.read_bytes()
            atomic_write_bytes(state_path, b'{"schema_version":')
            try:
                with pytest.raises(ConflictError, match="invalid"):
                    sdk.snapshot(run_id)
            finally:
                atomic_write_bytes(state_path, contents)
            assert sdk.snapshot(run_id).run.plan_version == 1
    completed = _child(git_repo, worktrees, run_id, "complete", tmp_path / "complete.json", audit)
    assert completed["state"] == "COMPLETED"
    assert completed["commit_sha"] == barriers["git_prepare"]["value"]
    assert completed["commit_sha"] == barriers["git_attach"]["value"]
    final = sdk.snapshot(run_id)
    assert final.run.repair_iteration == 1
    effects = [json.loads(line) for line in audit.read_text().splitlines()]
    provider_ids = [effect["identity"] for effect in effects if effect["kind"] == "provider"]
    assert len(provider_ids) == len(set(provider_ids)), "Completed model call was repeated"
    writes = Counter(effect["identity"] for effect in effects if effect["kind"] == "write")
    assert writes["main.py"] == 2  # Initial implementation and the explicit repair task only.
    assert writes["README.md"] == 2  # Unreceipted effect is safely replaced after the kill.
    with factory() as uow:
        workspace = uow.execution.workspace(run_id)
        assert workspace is not None
        assert len(uow.execution.tools(run_id)) == 2
        assert len(uow.execution.reviews(run_id)) == 2
        assert len(uow.delivery.artifacts(run_id)) >= 1
        events = uow.events.list(run_id)
        assert tuple(events[: len(previous_events)]) == previous_events
        assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert (workspace.path / "README.md").read_text().count(f"orqalis:{run_id}:begin") == 1
    assert (workspace.path / "main.py").read_text() == "answer = 43\n"
    assert (git_repo / "main.py").read_text() == "answer = 42\n"
    assert (
        fixture_git(workspace.path, "rev-list", "--count", f"{prepared.run.base_commit}..HEAD")
        == "1"
    )


@pytest.mark.parametrize(
    "case", ["live", "delayed", "persistent", "wait_budget", "kill_budget", "late", "error"]
)
def test_controller_termination_shares_budget_and_preserves_exclusion(
    monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    clock = SimpleNamespace(now=0.0)
    sleeps: list[float] = []
    probes: list[tuple[float, bool]] = []
    alive = True

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.now += seconds

    monkeypatch.setattr(
        sys.modules[__name__], "time", SimpleNamespace(monotonic=lambda: clock.now, sleep=sleep)
    )
    process = Mock(spec=subprocess.Popen)
    process.poll.side_effect = lambda: None if alive else 0

    def kill() -> None:
        nonlocal alive
        alive = False
        if case == "kill_budget":
            clock.now = 30.0

    def wait(*, timeout: float) -> int:
        assert timeout <= 30
        clock.now += 0.0 if case == "kill_budget" else 30.0 if case == "wait_budget" else 29.94
        return -1

    process.kill.side_effect = kill
    process.wait.side_effect = wait

    def probe() -> bool:
        probes.append((clock.now, alive))
        if alive:
            return case == "live"
        if case == "error":
            raise OSError("unexpected native failure")
        if case == "late":
            clock.now = 30.1
            return True
        return case == "delayed" and clock.now >= 29.97

    if case == "delayed":
        _terminate_controller(cast(subprocess.Popen[bytes], process), probe)
        assert 29.97 <= clock.now <= 30
        assert len(probes) >= 3 and sleeps
    elif case == "error":
        with pytest.raises(OSError, match="unexpected native failure"):
            _terminate_controller(cast(subprocess.Popen[bytes], process), probe)
    else:
        with pytest.raises(AssertionError):
            _terminate_controller(cast(subprocess.Popen[bytes], process), probe)
        if case == "live":
            process.kill.assert_not_called()
            process.wait.assert_not_called()
        if case in {"wait_budget", "kill_budget"}:
            assert probes == [(0.0, True)] and not sleeps
        if case == "kill_budget":
            assert process.wait.call_args.kwargs["timeout"] == 0.0
        if case == "persistent":
            assert clock.now <= 30 and sleeps and all(step <= 0.02 for step in sleeps)
