from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from orqalis.api.app import create_app
from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.persistence.database import session_factory
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork
from orqalis.sdk import Orqalis

pytestmark = pytest.mark.postgres


def test_api_contract_and_websocket_reconnect(database: Engine, git_repo: Path) -> None:
    sdk = Orqalis(unit_of_work=lambda: SQLProjectUnitOfWork(session_factory(database)))
    project = sdk.initialize(git_repo)
    goal = GoalDraft(
        goal="Observe fixture",
        scope=("main.py",),
        definition_of_done=("file validated",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="File exists",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    )
    with TestClient(
        create_app(sdk), base_url="http://localhost", client=("127.0.0.1", 50000)
    ) as client:
        response = client.post(
            "/api/runs",
            json={
                "project_id": str(project.id),
                "request": "Observe fixture",
                "branch": "feature/observe",
                "goal": goal.model_dump(mode="json"),
            },
        )
        assert response.status_code == 200, response.text
        state = response.json()
        run_id, cursor = state["run"]["id"], state["last_event_sequence"]
        assert state["run"]["state"] == "GOAL_DEFINED"
        assert state["actors"][0]["session"]["actor_type"] == "ORCHESTRATOR"
        assert client.get(f"/api/runs/{run_id}/events?after={cursor}").json() == []
        assert client.get(f"/api/runs/{run_id}/metrics").json()["plan_completion"] == 0
        with client.websocket_connect(
            f"ws://localhost/ws/runs/{run_id}?after={cursor}",
            headers={"origin": "http://localhost"},
        ) as socket:
            message = socket.receive_json()
            assert message["type"] == "snapshot"
            assert message["snapshot"]["run"]["state"] == "GOAL_DEFINED"
            paused = client.post(f"/api/runs/{run_id}/pause", json={"idempotency_key": "pause-api"})
            assert paused.status_code == 200
            observed = socket.receive_json()
            assert observed["type"] == "events"
            assert any(event["event_type"] == "RUN_PAUSED" for event in observed["events"])
            refreshed = socket.receive_json()["snapshot"]
            assert refreshed["run"]["state"] == "PAUSED"
            cursor = refreshed["last_event_sequence"]
        with client.websocket_connect(f"ws://localhost/ws/runs/{run_id}?after={cursor}") as socket:
            reconnected = socket.receive_json()["snapshot"]
            assert reconnected["last_event_sequence"] == cursor
            assert reconnected["run"]["state"] == "PAUSED"
        assert client.get("/api/projects").json()[0]["id"]
        assert client.get(f"/api/runs/{run_id}/agents").json()
        assert client.get(f"/api/runs/{run_id}/acceptance").json()["criteria"]
        intervals = client.get(f"/api/runs/{run_id}/timeline").json()
        assert any(item["kind"] == "actor" for item in intervals)
        brain = client.get(f"/api/projects/{project.id}/brain").json()
        assert brain["freshness"]["fresh"]
        assert brain["freshness"]["indexed_commit"] == sdk.git.status(git_repo).head
        assert client.get(f"/api/runs/{run_id}/diff?path=main.py").status_code == 404
        assert client.get(f"/api/projects/{project.id}/brain?run_id={run_id}").status_code == 200


def test_api_denies_cross_origin_and_untrusted_host(database: Engine) -> None:
    sdk = Orqalis(unit_of_work=lambda: SQLProjectUnitOfWork(session_factory(database)))
    with TestClient(
        create_app(sdk), base_url="http://localhost", client=("127.0.0.1", 50000)
    ) as client:
        assert client.get("/health", headers={"host": "attacker.example"}).status_code == 400
        assert (
            client.post(
                "/api/projects/init",
                json={"repo": "/"},
                headers={"origin": "https://attacker.example"},
            ).status_code
            == 403
        )
        response = client.post("/api/runs", json={"secret": "must-not-echo"})
        assert response.status_code == 422
        assert "must-not-echo" not in response.text


def test_remote_client_cannot_bypass_loopback_policy_with_host_header(database: Engine) -> None:
    from uuid import uuid4

    from starlette.websockets import WebSocketDisconnect

    sdk = Orqalis(unit_of_work=lambda: SQLProjectUnitOfWork(session_factory(database)))
    with TestClient(
        create_app(sdk), base_url="http://localhost", client=("203.0.113.10", 50000)
    ) as client:
        assert client.get("/health").status_code == 403
        with (
            pytest.raises(WebSocketDisconnect) as error,
            client.websocket_connect(f"ws://localhost/ws/runs/{uuid4()}"),
        ):
            pass
        assert error.value.code == 1008
