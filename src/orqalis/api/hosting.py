import os
import subprocess
import sys
import time
import webbrowser

import httpx

from orqalis.api.app import frontend_directory
from orqalis.config.settings import Settings
from orqalis.domain.errors import ConflictError, PolicyDeniedError

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def local_url(settings: Settings) -> str:
    if settings.host not in _LOCAL_HOSTS:
        raise PolicyDeniedError("Remote UI binding requires authentication and is not enabled")
    host = f"[{settings.host}]" if settings.host == "::1" else settings.host
    return f"http://{host}:{settings.port}"


def ensure_server(settings: Settings, open_path: str | None = None) -> str:
    url = local_url(settings)
    if frontend_directory() is None:
        raise ConflictError(
            "Frontend assets are missing; reinstall Orqalis or rebuild the contributor UI"
        )
    with httpx.Client(timeout=1, trust_env=False) as client:

        def healthy() -> bool:
            try:
                response = client.get(f"{url}/health")
            except httpx.TransportError:
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
            return True

        if not healthy():
            child_env = dict(os.environ)
            child_env.update(
                {
                    "ORQALIS_HOST": settings.host,
                    "ORQALIS_PORT": str(settings.port),
                    "ORQALIS_DATABASE_URL": settings.database_url.get_secret_value(),
                }
            )
            process = subprocess.Popen(
                [sys.executable, "-I", "-m", "orqalis", "serve"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=child_env,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
                start_new_session=os.name != "nt",
            )
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if healthy():
                    break
                if process.poll() is not None:
                    raise ConflictError(
                        "UI host exited; run orqalis serve to inspect the startup error"
                    )
                time.sleep(0.2)
            else:
                raise ConflictError("UI host did not become healthy; run orqalis serve to inspect")
    if open_path is not None:
        webbrowser.open(url + open_path)
    return url
