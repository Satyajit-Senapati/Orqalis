from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orqalis.api.app import create_app
from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.memory.curated import CuratedMemoryStore, MemoryCategory, MemoryProvenance
from orqalis.persistence.filesystem import ProjectLayout
from orqalis.sdk import Orqalis


def test_api_contract_and_websocket_reconnect(git_repo: Path) -> None:
    sdk = Orqalis(root=git_repo)
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
        catalog = client.get("/api/skills").json()
        assert len(catalog) >= 3 and all(item["source"] == "bundled" for item in catalog)
        assert all("instructions" not in item["metadata"] for item in catalog)
        complete_events = client.get(f"/api/runs/{run_id}/events").json()
        assert client.get(f"/api/runs/{run_id}/events?limit=2").json() == complete_events[:2]
        assert client.get(f"/api/runs/{run_id}/events?limit=1001").status_code == 422
        assert state["skill_activity"] == []
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
        context = client.post(
            f"/api/projects/{project.id}/context",
            json={"task": "Python architecture", "max_chars": 200000},
        )
        assert context.status_code == 200
        assert context.json()["project_id"] == str(project.id)
        memory = client.get(f"/api/projects/{project.id}/memory?query=Python&limit=5")
        assert memory.status_code == 200 and isinstance(memory.json(), list)
        assert client.get(f"/api/projects/{project.id}/memory?limit=0").status_code == 422
        assert (
            client.get(
                f"/api/projects/{project.id}/memory", params={"query": "x" * 10001}
            ).status_code
            == 422
        )
        assert (
            client.post(f"/api/projects/{project.id}/context", json={"task": ""}).status_code == 422
        )
        assert brain["freshness"]["indexed_commit"] == sdk.git.status(git_repo).head
        assert client.get(f"/api/runs/{run_id}/diff?path=main.py").status_code == 404
        assert client.get(f"/api/projects/{project.id}/brain?run_id={run_id}").status_code == 200


def test_api_memory_returns_only_approved_curated_records(git_repo: Path) -> None:
    sdk = Orqalis(root=git_repo)
    try:
        project = sdk.initialize(git_repo)
        store = CuratedMemoryStore(ProjectLayout(git_repo))
        record = store.new_record(
            MemoryCategory.CONVENTIONS,
            "Authoritative naming convention",
            "The aurora-marker identifies curated naming guidance.",
            MemoryProvenance(type="user"),
        )
        proposal = store.propose(record, "Document a durable project convention")
        store.approve(proposal.id, "Repository evidence confirms the convention")
        assert tuple(
            (git_repo / ".orqalis" / "cache" / "search" / "source-records").glob("SRC-*.md")
        )
        replacement = store.new_record(
            MemoryCategory.CONVENTIONS,
            "Updated naming convention",
            "The aurora-marker now identifies reviewed naming guidance.",
            MemoryProvenance(type="user"),
        )
        pending = store.propose(replacement, "Update the accepted convention", supersedes=record.id)

        with TestClient(
            create_app(sdk), base_url="http://localhost", client=("127.0.0.1", 50000)
        ) as client:
            response = client.get(
                f"/api/projects/{project.id}/memory",
                params={"query": "aurora-marker", "limit": 10},
            )
            assert response.status_code == 200, response.text
            # Lifecycle fields are additive; pending proposals remain excluded.
            assert response.json() == [
                {
                    "record": record.model_dump(mode="json"),
                    "freshness": "FRESH",
                    "changed_sources": [],
                    "lifecycle": "ACTIVE",
                    "superseded_by": None,
                }
            ]
            assert all("item" not in value for value in response.json())

            approved = store.approve(pending.id, "Reviewed the replacement convention")
            updated = client.get(
                f"/api/projects/{project.id}/memory",
                params={"query": "aurora-marker", "limit": 10},
            )
            assert updated.status_code == 200, updated.text
            assert updated.json() == [
                {
                    "record": approved.record.model_dump(mode="json"),
                    "freshness": "FRESH",
                    "changed_sources": [],
                    "lifecycle": "ACTIVE",
                    "superseded_by": None,
                }
            ]
            # Supersession filters default retrieval without destroying history.
            historical = sdk.get_project_memory(record.id)
            assert historical.item.lifecycle == "SUPERSEDED"
            assert historical.item.superseded_by == replacement.id
    finally:
        sdk.close()


def test_api_denies_cross_origin_and_untrusted_host(git_repo: Path) -> None:
    sdk = Orqalis(root=git_repo)
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
        malformed_origin = client.post(
            "/api/projects/init", json={"repo": "/"}, headers={"origin": "http://localhost:invalid"}
        )
        assert malformed_origin.status_code == 403


def test_remote_client_cannot_bypass_loopback_policy_with_host_header(git_repo: Path) -> None:
    from uuid import uuid4

    from starlette.websockets import WebSocketDisconnect

    sdk = Orqalis(root=git_repo)
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


@pytest.mark.parametrize("blocked_stage", ["snapshot", "events", "notification"])
def test_websocket_disconnect_releases_subscription_during_pending_work(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, blocked_stage: str
) -> None:
    import asyncio
    import threading
    from uuid import UUID

    from starlette.routing import WebSocketRoute
    from starlette.types import Message
    from starlette.websockets import WebSocket

    from orqalis.domain.approval import ControlMode
    from orqalis.domain.events import Event
    from orqalis.domain.projections import RunSnapshot

    sdk = Orqalis(root=git_repo)
    project = sdk.initialize(git_repo)
    run = sdk.goals.create_pending(
        project,
        "Disconnect lifecycle",
        "feature/disconnect",
        sdk.git.status(git_repo).head,
        ControlMode.AUTONOMOUS,
        None,
    )
    state = sdk.snapshot(run.id)
    entered = threading.Event()
    release = threading.Event()
    event_reads: list[int] = []

    def snapshot(run_id: UUID) -> RunSnapshot:
        if blocked_stage == "snapshot":
            entered.set()
            assert release.wait(4)
        return state

    def events(run_id: UUID, after: int = 0, limit: int | None = None) -> tuple[Event, ...]:
        event_reads.append(after)
        if blocked_stage == "events":
            entered.set()
            assert release.wait(4)
        return ()

    monkeypatch.setattr(sdk, "snapshot", snapshot)
    monkeypatch.setattr(sdk, "events", events)

    async def exercise() -> None:
        messages: asyncio.Queue[Message] = asyncio.Queue()
        messages.put_nowait({"type": "websocket.connect"})
        snapshot_sent = asyncio.Event()

        async def receive() -> Message:
            return await messages.get()

        async def send(message: Message) -> None:
            if message["type"] == "websocket.send" and '"type":"snapshot"' in message["text"]:
                snapshot_sent.set()

        socket = WebSocket(
            {
                "type": "websocket",
                "scheme": "ws",
                "path": f"/ws/runs/{run.id}",
                "query_string": b"",
                "headers": [],
                "server": ("127.0.0.1", 9000),
                "client": ("127.0.0.1", 30000),
                "subprotocols": [],
            },
            receive,
            send,
        )
        app = create_app(sdk)
        endpoint = next(
            route.endpoint
            for route in app.routes
            if isinstance(route, WebSocketRoute) and route.path == "/ws/runs/{run_id}"
        )
        stream = asyncio.create_task(endpoint(socket, run.id, 0))
        try:
            if blocked_stage == "notification":
                await asyncio.wait_for(snapshot_sent.wait(), 2)
            else:
                assert await asyncio.to_thread(entered.wait, 2)
            messages.put_nowait({"type": "websocket.disconnect", "code": 1000})
            await asyncio.wait_for(asyncio.shield(stream), 0.5)
            assert run.id not in sdk.event_bus._subscribers
            if blocked_stage == "snapshot":
                assert event_reads == []
        finally:
            # A cancelled coroutine cannot kill a filesystem worker; let it finish safely.
            release.set()
            await asyncio.wait_for(stream, 2)

    try:
        asyncio.run(exercise())
    finally:
        sdk.close()


@pytest.mark.parametrize("cancellation", ["transport", "native"])
def test_websocket_transport_cancellation_preserves_cleanup(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, cancellation: str
) -> None:
    import asyncio

    from anyio import CancelScope
    from starlette.routing import WebSocketRoute
    from starlette.types import Message
    from starlette.websockets import WebSocket

    from orqalis.domain.approval import ControlMode
    from orqalis.observability.event_bus import EventNotification, EventSubscription

    sdk = Orqalis(root=git_repo)
    project = sdk.initialize(git_repo)
    run = sdk.goals.create_pending(
        project,
        "Transport cancellation lifecycle",
        "feature/transport-cancel",
        sdk.git.status(git_repo).head,
        ControlMode.AUTONOMOUS,
        None,
    )
    original_receive = EventSubscription.receive

    async def exercise() -> None:
        messages: asyncio.Queue[Message] = asyncio.Queue()
        messages.put_nowait({"type": "websocket.connect"})
        waiting = asyncio.Event()
        cleanup_started = asyncio.Event()
        cleanup_finished = asyncio.Event()
        release_cleanup = asyncio.Event()
        scopes: list[CancelScope] = []

        async def subscription_receive(
            subscription: EventSubscription, timeout: float | None = None
        ) -> EventNotification:
            waiting.set()
            try:
                return await original_receive(subscription, timeout)
            finally:
                # A real subscription wait may suspend while cancelling its queue wait.
                # Place transport cancellation precisely inside this finalization.
                cleanup_started.set()
                await release_cleanup.wait()
                cleanup_finished.set()

        monkeypatch.setattr(EventSubscription, "receive", subscription_receive)

        async def receive() -> Message:
            return await messages.get()

        async def send(message: Message) -> None:
            pass

        socket = WebSocket(
            {
                "type": "websocket",
                "scheme": "ws",
                "path": f"/ws/runs/{run.id}",
                "query_string": b"",
                "headers": [],
                "server": ("127.0.0.1", 9000),
                "client": ("127.0.0.1", 30000),
                "subprotocols": [],
            },
            receive,
            send,
        )
        app = create_app(sdk)
        endpoint = next(
            route.endpoint
            for route in app.routes
            if isinstance(route, WebSocketRoute) and route.path == "/ws/runs/{run_id}"
        )

        async def serve() -> None:
            with CancelScope() as scope:
                scopes.append(scope)
                await endpoint(socket, run.id, 0)
                await asyncio.sleep(0)

        stream = asyncio.create_task(serve())
        try:
            await asyncio.wait_for(waiting.wait(), 2)
            if cancellation == "transport":
                messages.put_nowait({"type": "websocket.disconnect", "code": 1000})
            else:
                stream.cancel("native-stop")
            await asyncio.wait_for(cleanup_started.wait(), 2)
            assert not cleanup_finished.is_set()
            if cancellation == "transport":
                scopes[0].cancel()
            release_cleanup.set()
            if cancellation == "transport":
                await asyncio.wait_for(asyncio.shield(stream), 0.5)
                assert scopes[0].cancelled_caught
            else:
                with pytest.raises(asyncio.CancelledError, match="native-stop"):
                    await asyncio.wait_for(stream, 0.5)
                assert not scopes[0].cancelled_caught
            assert cleanup_finished.is_set()
            assert sdk.event_bus.subscriber_count(run.id) == 0
        finally:
            release_cleanup.set()
            if not stream.done():
                stream.cancel()
            await asyncio.gather(stream, return_exceptions=True)

    try:
        asyncio.run(exercise())
    finally:
        sdk.close()
