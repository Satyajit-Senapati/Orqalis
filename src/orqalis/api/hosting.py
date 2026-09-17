"""Terminal-owned hosting for the optional local control center."""

import socket
import threading
import time
import webbrowser
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

import httpx
import uvicorn

from orqalis import __version__
from orqalis.api.app import create_app, frontend_directory
from orqalis.api.scope import project_scope_id
from orqalis.config.settings import Settings
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.persistence.filesystem import resolve_project_root

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_STARTUP_TIMEOUT = 15.0
_SHUTDOWN_TIMEOUT = 10.0


def local_url(settings: Settings) -> str:
    if settings.host not in _LOCAL_HOSTS:
        raise PolicyDeniedError("Remote UI binding requires authentication and is not enabled")
    host = f"[{settings.host}]" if settings.host == "::1" else settings.host
    return f"http://{host}:{settings.port}"


@dataclass(slots=True)
class UISession:
    """A local UI listener, owned by this CLI invocation or reused from another one."""

    url: str
    owned: bool
    _server: uvicorn.Server | None = field(default=None, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)
    _failure: list[Exception] = field(default_factory=list, repr=False)

    def wait(self) -> None:
        """Keep an owned listener attached to the invoking terminal."""
        if self._thread is not None:
            try:
                while self._thread.is_alive():
                    self._thread.join(timeout=0.2)
            except KeyboardInterrupt:
                return  # Context exit will stop and join the owned listener.
            if self._failure:
                raise ConflictError("The local UI host stopped unexpectedly") from self._failure[0]

    def close(self) -> None:
        """Stop only the listener started by this session."""
        if self._server is None or self._thread is None:
            return
        self._server.should_exit = True
        self._thread.join(timeout=_SHUTDOWN_TIMEOUT)
        if self._thread.is_alive():
            self._server.force_exit = True
            self._thread.join(timeout=2)
        if self._thread.is_alive():
            raise ConflictError("The local UI host did not stop cleanly")


def _port_open(settings: Settings) -> bool:
    try:
        with socket.create_connection((settings.host, settings.port), timeout=0.5):
            return True
    except OSError:
        return False


def _healthy(
    client: httpx.Client,
    url: str,
    settings: Settings,
    expected_scope: str,
    *,
    starting: bool = False,
) -> bool:
    try:
        response = client.get(f"{url}/health")
    except httpx.TransportError as exc:
        if not starting and _port_open(settings):
            raise ConflictError("The configured UI port belongs to another service") from exc
        return False
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if (
        response.status_code != 200
        or not isinstance(payload, dict)
        or payload.get("service") != "orqalis"
    ):
        raise ConflictError("The configured UI port belongs to another service")
    if payload.get("version") != __version__:
        raise ConflictError(
            "A different Orqalis version owns the UI port; stop it before starting this version"
        )
    if payload.get("project_scope") != expected_scope:
        raise ConflictError(
            "A different Orqalis project owns the UI port; stop it or choose another port"
        )
    return True


@contextmanager
def ui_session(settings: Settings, open_path: str | None = None) -> Iterator[UISession]:
    """Start a foreground-owned UI host or reuse an already healthy local host.

    No subprocess, service, startup entry or persistent background daemon is created.
    The owned listener is stopped even when browser opening or the caller fails.
    """
    url = local_url(settings)
    root = resolve_project_root(settings.project_root)
    expected_scope = project_scope_id(root)
    assert expected_scope is not None
    if frontend_directory() is None:
        raise ConflictError(
            "Frontend assets are missing; reinstall Orqalis or rebuild the contributor UI"
        )

    session: UISession | None = None
    try:
        with httpx.Client(timeout=1, trust_env=False) as client:
            if _healthy(client, url, settings, expected_scope):
                session = UISession(url=url, owned=False)
            else:
                server = uvicorn.Server(
                    uvicorn.Config(
                        create_app(root=root),
                        host=settings.host,
                        port=settings.port,
                        log_level=settings.log_level.lower(),
                    )
                )
                failure: list[Exception] = []

                def run_server() -> None:
                    try:
                        server.run()
                    except Exception as exc:
                        failure.append(exc)

                thread = threading.Thread(target=run_server, name="orqalis-ui", daemon=True)
                thread.start()
                session = UISession(
                    url=url, owned=True, _server=server, _thread=thread, _failure=failure
                )
                deadline = time.monotonic() + _STARTUP_TIMEOUT
                while time.monotonic() < deadline:
                    if (
                        _healthy(client, url, settings, expected_scope, starting=True)
                        and server.started
                    ):
                        break
                    if not thread.is_alive():
                        if failure:
                            raise ConflictError("The local UI host could not start") from failure[0]
                        raise ConflictError(
                            "The local UI host exited; check whether the configured port is in use"
                        )
                    time.sleep(0.2)
                else:
                    raise ConflictError("The local UI host did not become healthy")

        if open_path is not None:
            webbrowser.open(url + open_path)
        assert session is not None
        yield session
    finally:
        if session is not None:
            session.close()
