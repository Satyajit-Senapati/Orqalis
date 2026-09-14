import subprocess
from unittest.mock import Mock

import httpx
import pytest
from pydantic import ValidationError

from orqalis.api.app import ContextRequest, origin_allowed
from orqalis.api.hosting import ensure_server
from orqalis.config.settings import Settings


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


def test_background_ui_preserves_python_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    import orqalis.api.hosting as hosting

    process = Mock(spec=subprocess.Popen)
    process.poll.return_value = None
    launch = Mock(return_value=process)
    requests = 0

    def transport(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            raise httpx.ConnectError("not listening", request=request)
        return httpx.Response(200, json={"service": "orqalis", "version": "1.0.0"})

    client = httpx.Client(transport=httpx.MockTransport(transport))
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: client)
    monkeypatch.setattr(subprocess, "Popen", launch)
    monkeypatch.setattr(hosting, "frontend_directory", lambda: object())
    assert ensure_server(Settings()) == "http://127.0.0.1:7842"
    assert launch.call_args.args[0][1:] == ["-I", "-m", "orqalis", "serve"]


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
