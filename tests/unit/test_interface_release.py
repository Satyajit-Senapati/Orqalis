import subprocess
import threading
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
import uvicorn
from pydantic import ValidationError

import orqalis.api.hosting as hosting
from orqalis import __version__
from orqalis.api.app import ContextRequest, origin_allowed
from orqalis.api.hosting import ui_session
from orqalis.config.settings import Settings
from orqalis.domain.errors import ConflictError

_PROJECT_SCOPE = "test-project-scope"


@pytest.mark.parametrize(
    "origin",
    [
        "http://[broken",
        "http://localhost:invalid",
        "http://localhost:99999",
        "https://attacker.invalid",
    ],
)
def test_malformed_origin_fails_closed(origin: str) -> None:
    assert not origin_allowed(origin, "http://localhost:7842")


def _mock_health(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> None:
    real_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(hosting, "frontend_directory", lambda: object())
    monkeypatch.setattr(hosting, "_port_open", lambda settings: False)
    monkeypatch.setattr(hosting, "resolve_project_root", lambda root: Path.cwd())
    monkeypatch.setattr(hosting, "project_scope_id", lambda root: _PROJECT_SCOPE)


def test_ui_reuses_existing_host_without_taking_ownership(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_health(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={
                "service": "orqalis",
                "version": __version__,
                "project_scope": _PROJECT_SCOPE,
            },
        ),
    )
    create_app = Mock(side_effect=AssertionError("must not start another host"))
    monkeypatch.setattr(hosting, "create_app", create_app)
    browser = Mock()
    monkeypatch.setattr(webbrowser, "open", browser)

    with ui_session(Settings(), "/runs/example") as session:
        assert session.url == "http://127.0.0.1:7842"
        assert not session.owned
        session.wait()

    create_app.assert_not_called()
    browser.assert_called_once_with("http://127.0.0.1:7842/runs/example")


def _mock_owned_server(monkeypatch: pytest.MonkeyPatch) -> tuple[threading.Event, threading.Event]:
    running = threading.Event()
    stopped = threading.Event()

    class FakeServer:
        def __init__(self, config: object) -> None:
            self.should_exit = False
            self.force_exit = False
            self.started = False

        def run(self) -> None:
            self.started = True
            running.set()
            while not self.should_exit:
                time.sleep(0.005)
            stopped.set()

    def health(request: httpx.Request) -> httpx.Response:
        if not running.is_set():
            raise httpx.ConnectError("not listening", request=request)
        return httpx.Response(
            200,
            json={
                "service": "orqalis",
                "version": __version__,
                "project_scope": _PROJECT_SCOPE,
            },
        )

    _mock_health(monkeypatch, health)
    monkeypatch.setattr(uvicorn, "Config", lambda *args, **kwargs: object())
    monkeypatch.setattr(uvicorn, "Server", FakeServer)
    monkeypatch.setattr(hosting, "create_app", lambda **kwargs: object())
    return running, stopped


def test_ui_owned_host_stays_in_process_and_stops_on_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    running, stopped = _mock_owned_server(monkeypatch)
    process = Mock(side_effect=AssertionError("must not spawn a child process"))
    monkeypatch.setattr(subprocess, "Popen", process)

    with ui_session(Settings()) as session:
        assert session.owned
        assert running.is_set()
        assert not stopped.is_set()

    assert stopped.wait(timeout=1)
    process.assert_not_called()


def test_ui_wait_blocks_until_owned_host_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    _, stopped = _mock_owned_server(monkeypatch)

    with ui_session(Settings()) as session:
        timer = threading.Timer(0.05, lambda: setattr(session._server, "should_exit", True))
        timer.start()
        session.wait()
        timer.join(timeout=1)
        assert stopped.is_set()


def test_ui_ctrl_c_returns_to_prompt_and_closes_owned_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, stopped = _mock_owned_server(monkeypatch)

    with ui_session(Settings()) as session:
        thread = session._thread
        assert thread is not None
        original_join = thread.join
        interrupted = False

        def interrupt_once(timeout: float | None = None) -> None:
            nonlocal interrupted
            if not interrupted:
                interrupted = True
                raise KeyboardInterrupt
            original_join(timeout)

        monkeypatch.setattr(thread, "join", interrupt_once)
        session.wait()
        assert interrupted

    assert stopped.wait(timeout=1)


def test_ui_startup_failure_does_not_leave_a_host(monkeypatch: pytest.MonkeyPatch) -> None:
    stopped = threading.Event()

    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("not listening", request=request)

    class FailedServer:
        started = False
        should_exit = False
        force_exit = False

        def __init__(self, config: object) -> None:
            pass

        def run(self) -> None:
            stopped.set()

    _mock_health(monkeypatch, unavailable)
    monkeypatch.setattr(uvicorn, "Config", lambda *args, **kwargs: object())
    monkeypatch.setattr(uvicorn, "Server", FailedServer)
    monkeypatch.setattr(hosting, "create_app", lambda **kwargs: object())

    with pytest.raises(ConflictError, match="exited"), ui_session(Settings()):
        pass

    assert stopped.is_set()


def test_ui_owned_host_stops_when_browser_open_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _, stopped = _mock_owned_server(monkeypatch)
    monkeypatch.setattr(webbrowser, "open", Mock(side_effect=RuntimeError("browser failed")))

    with pytest.raises(RuntimeError, match="browser failed"), ui_session(Settings(), "/"):
        pass

    assert stopped.wait(timeout=1)


def test_ui_rejects_foreign_service_on_configured_port(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_health(monkeypatch, lambda request: httpx.Response(200, json={"service": "foreign"}))
    create_app = Mock(side_effect=AssertionError("must not start a host"))
    monkeypatch.setattr(hosting, "create_app", create_app)

    with pytest.raises(ConflictError, match="another service"), ui_session(Settings()):
        pass

    create_app.assert_not_called()


def test_ui_rejects_a_different_installed_version(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_health(
        monkeypatch,
        lambda request: httpx.Response(200, json={"service": "orqalis", "version": "0.0.0"}),
    )
    with pytest.raises(ConflictError, match="different Orqalis version"), ui_session(Settings()):
        pass


def test_ui_rejects_an_orqalis_host_for_another_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_health(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={
                "service": "orqalis",
                "version": __version__,
                "project_scope": "another-project",
            },
        ),
    )
    create_app = Mock(side_effect=AssertionError("must not reuse or replace the other project"))
    monkeypatch.setattr(hosting, "create_app", create_app)

    with pytest.raises(ConflictError, match="different Orqalis project"), ui_session(Settings()):
        pass

    create_app.assert_not_called()


def test_ui_rejects_occupied_non_http_port(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.RemoteProtocolError("invalid HTTP", request=request)

    _mock_health(monkeypatch, unavailable)
    monkeypatch.setattr(hosting, "_port_open", lambda settings: True)

    with pytest.raises(ConflictError, match="another service"), ui_session(Settings()):
        pass


@pytest.mark.parametrize("budget", [1000, 200000])
def test_api_context_budget_matches_shared_service(budget: int) -> None:
    assert ContextRequest(task="Inspect architecture", max_chars=budget).max_chars == budget


@pytest.mark.parametrize("budget", [999, 200001])
def test_api_context_budget_rejects_outside_shared_service_bounds(budget: int) -> None:
    with pytest.raises(ValidationError):
        ContextRequest(task="Inspect architecture", max_chars=budget)


def test_api_context_task_matches_memory_query_limit() -> None:
    assert len(ContextRequest(task="x" * 10000).task) == 10000
    with pytest.raises(ValidationError):
        ContextRequest(task="x" * 10001)
