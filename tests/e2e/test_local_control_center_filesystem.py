"""Local Control Center regressions against the authoritative filesystem store."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orqalis.api.app import create_app
from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.persistence.filesystem import TaskCapsuleStore
from orqalis.sdk import Orqalis


def _git(repo: Path, *arguments: str) -> None:
    environment = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Orqalis Control Center Test",
        "GIT_AUTHOR_EMAIL": "control-center@orqalis.invalid",
        "GIT_COMMITTER_NAME": "Orqalis Control Center Test",
        "GIT_COMMITTER_EMAIL": "control-center@orqalis.invalid",
        "GIT_TERMINAL_PROMPT": "0",
    }
    subprocess.run(
        [
            "git",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-c",
            "commit.gpgsign=false",
            "-C",
            str(repo),
            *arguments,
        ],
        env=environment,
        capture_output=True,
        check=True,
        text=True,
    )


def _repository(parent: Path) -> Path:
    root = parent / "control-center"
    root.mkdir()
    _git(root, "init", "-b", "main")
    (root / "main.py").write_text("def visible():\n    return True\n", encoding="utf-8")
    (root / "README.md").write_text("# Control Center fixture\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "test: create control center fixture")
    return root


def _goal() -> GoalDraft:
    return GoalDraft(
        goal="Keep the local run observable",
        scope=("main.py",),
        definition_of_done=("The source remains visible",),
        criteria=(
            CriterionDefinition(
                key="AC-source",
                description="main.py defines visible",
                validation_spec=FileValidation(path="main.py", contains="visible"),
            ),
        ),
    )


@pytest.fixture()
def no_database_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "DATABASE_URL",
        "ORQALIS_DATABASE_URL",
        "POSTGRES_HOST",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    ):
        monkeypatch.delenv(name, raising=False)


def test_control_center_replays_broadcasts_and_restarts_from_task_capsule(
    tmp_path: Path, no_database_environment: None
) -> None:
    root = _repository(tmp_path)
    first = Orqalis(root=root)
    project = first.initialize(root)

    with TestClient(
        create_app(first), base_url="http://localhost", client=("127.0.0.1", 50000)
    ) as client:
        started = client.post(
            "/api/runs",
            json={
                "project_id": str(project.id),
                "request": "Exercise local Control Center persistence",
                "branch": "feature/control-center",
                "goal": _goal().model_dump(mode="json"),
            },
        )
        assert started.status_code == 200, started.text
        snapshot = started.json()
        run_id = snapshot["run"]["id"]
        cursor = snapshot["last_event_sequence"]

        # A late client receives the authoritative snapshot after replaying any
        # events following its cursor, then receives committed live events.
        with client.websocket_connect(
            f"ws://localhost/ws/runs/{run_id}?after={cursor}",
            headers={"origin": "http://localhost"},
        ) as socket:
            initial = socket.receive_json()
            assert initial["type"] == "snapshot"
            assert initial["snapshot"]["last_event_sequence"] == cursor

            paused = client.post(
                f"/api/runs/{run_id}/pause", json={"idempotency_key": "pause-local"}
            )
            assert paused.status_code == 200, paused.text
            events = socket.receive_json()
            assert events["type"] == "events"
            assert any(event["event_type"] == "RUN_PAUSED" for event in events["events"])
            current = socket.receive_json()
            assert current["type"] == "snapshot"
            assert current["snapshot"]["run"]["state"] == "PAUSED"
            cursor = current["snapshot"]["last_event_sequence"]

        capsule_id = TaskCapsuleStore.from_root(root).capsule_id(current["snapshot"]["run"]["id"])
        assert capsule_id is not None
        assert (root / ".orqalis" / "tasks" / capsule_id).is_dir()
        capsules = client.get("/api/tasks")
        assert capsules.status_code == 200, capsules.text
        assert capsules.json()[0]["id"] == capsule_id
        capsule = client.get(f"/api/tasks/{capsule_id}")
        assert capsule.status_code == 200, capsule.text
        assert capsule.json()["task"]["run_id"] == run_id
        assert capsule.json()["event_count"] == cursor

    first.close()

    # The second process has no reference to the first SDK or event bus. Its API
    # reconstructs history from the capsule and accepts the persisted cursor.
    second = Orqalis(root=root)
    try:
        with TestClient(
            create_app(second), base_url="http://localhost", client=("127.0.0.1", 50001)
        ) as client:
            historical = client.get(f"/api/runs/{run_id}")
            assert historical.status_code == 200, historical.text
            assert historical.json()["run"]["state"] == "PAUSED"
            assert client.get("/api/runs").json()[0]["id"] == run_id
            assert client.get(f"/api/tasks/{capsule_id}").json()["task"]["status"] == "PAUSED"
            durable = client.get(f"/api/runs/{run_id}/events").json()
            assert durable[-1]["sequence"] == cursor
            with client.websocket_connect(
                f"ws://localhost/ws/runs/{run_id}?after={cursor}",
                headers={"origin": "http://localhost"},
            ) as socket:
                recovered = socket.receive_json()
                assert recovered["type"] == "snapshot"
                assert recovered["snapshot"]["last_event_sequence"] == cursor
    finally:
        second.close()
