import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.resources import files
from ipaddress import ip_address
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from orqalis import __version__
from orqalis.api.contracts import AcceptanceView, RunMetrics
from orqalis.delivery.inspection import DiffView
from orqalis.domain.acceptance import GoalDraft
from orqalis.domain.base import Contract
from orqalis.domain.capabilities import SkillCatalogEntry
from orqalis.domain.errors import OrqalisError
from orqalis.domain.events import Event
from orqalis.domain.memory import ContextPack, MemoryMatch, ProjectBrain
from orqalis.domain.project import Project
from orqalis.domain.projections import ActorProjection, RunSnapshot
from orqalis.domain.run import Run
from orqalis.domain.task import Task
from orqalis.domain.telemetry import TimelineSegment
from orqalis.sdk import Orqalis
from orqalis.security.redaction import safe_diagnostic

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class InitRequest(Contract):
    repo: Path


class ContextRequest(Contract):
    task: str = Field(min_length=1, max_length=10000)
    max_chars: int = Field(default=20000, ge=1000, le=200000)


class StartRequest(Contract):
    project_id: UUID
    request: str
    branch: str
    goal: GoalDraft


class RecoveryRequest(Contract):
    execution_id: UUID
    reason: str
    idempotency_key: str
    acknowledge_uncertainty: bool = False


class CommandRequest(Contract):
    idempotency_key: str


def loopback_client(host: str | None) -> bool:
    if host is None:
        return False
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def origin_allowed(origin: str | None, request_url: str) -> bool:
    if origin is None:
        return True  # Native local SDK/CLI requests do not send Origin.
    try:
        parsed, target = urlparse(origin), urlparse(request_url)
        return (
            parsed.scheme in {"http", "https"}
            and parsed.hostname in _LOCAL_HOSTS
            and parsed.hostname == target.hostname
            and parsed.port == target.port
        )
    except ValueError:
        return False


def frontend_directory() -> Path | None:
    packaged = Path(str(files("orqalis").joinpath("web")))
    development = Path(__file__).resolve().parents[3] / "web" / "dist"
    return next((path for path in (development, packaged) if (path / "index.html").is_file()), None)


def create_app(client: Orqalis | None = None) -> FastAPI:
    owns_client = client is None
    sdk = client or Orqalis()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if owns_client:
            sdk.close()

    app = FastAPI(title="Orqalis Local API", version=__version__, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])

    @app.middleware("http")
    async def local_origin(request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not loopback_client(request.client.host if request.client else None):
            return JSONResponse({"code": "remote_access_denied"}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and (
            not origin_allowed(request.headers.get("origin"), str(request.url))
            or request.headers.get("sec-fetch-site") == "cross-site"
        ):
            return JSONResponse({"code": "origin_denied"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; connect-src 'self' ws://localhost:* ws://127.0.0.1:*; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"
        )
        return response

    @app.exception_handler(OrqalisError)
    async def domain_error(_: Request, exc: OrqalisError) -> JSONResponse:
        status = {"not_found": 404, "conflict": 409, "policy_denied": 403, "invalid_input": 422}
        return JSONResponse(
            {"code": exc.code, "message": safe_diagnostic(str(exc))},
            status_code=status.get(exc.code, 400),
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        return JSONResponse({"code": "database_unavailable"}, status_code=503)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            {"code": "invalid_request", "message": "Request does not match the API contract"},
            status_code=422,
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"service": "orqalis", "version": __version__}

    @app.get("/api/skills")
    def skills() -> tuple[SkillCatalogEntry, ...]:
        return sdk.list_skills()

    @app.get("/api/projects")
    def projects() -> tuple[Project, ...]:
        return sdk.list_projects()

    @app.post("/api/projects/init")
    def initialize(command: InitRequest) -> Project:
        return sdk.initialize(command.repo)

    @app.get("/api/projects/{project_id}")
    def project(project_id: UUID) -> Project:
        return sdk.get_project(project_id)

    @app.post("/api/projects/{project_id}/context")
    def context(project_id: UUID, command: ContextRequest) -> ContextPack:
        return sdk.memory.context(sdk.get_project(project_id), command.task, command.max_chars)

    @app.get("/api/projects/{project_id}/memory")
    def memory(
        project_id: UUID,
        query: Annotated[str, Query(max_length=10000)] = "",
        limit: Annotated[int, Query(ge=1, le=100)] = 10,
    ) -> tuple[MemoryMatch, ...]:
        return sdk.memory.search(sdk.get_project(project_id), query, limit)

    @app.get("/api/projects/{project_id}/brain")
    def brain(project_id: UUID, query: str = "", run_id: UUID | None = None) -> ProjectBrain:
        return sdk.brain.get(project_id, query, run_id)

    @app.get("/api/runs/{run_id}/timeline")
    def timeline_view(run_id: UUID) -> tuple[TimelineSegment, ...]:
        return sdk.snapshot(run_id).timeline

    @app.get("/api/runs/{run_id}/diff")
    def diff_view(run_id: UUID, path: str) -> DiffView:
        return sdk.changes.diff(run_id, path)

    @app.get("/api/runs")
    def runs(project_id: UUID | None = None) -> tuple[Run, ...]:
        return sdk.list_runs(project_id)

    @app.post("/api/runs")
    def start(command: StartRequest) -> RunSnapshot:
        return sdk.prepare_run(command.project_id, command.request, command.branch, command.goal)

    @app.get("/api/runs/{run_id}")
    def snapshot(run_id: UUID) -> RunSnapshot:
        return sdk.snapshot(run_id)

    @app.get("/api/runs/{run_id}/events")
    def events(
        run_id: UUID,
        after: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
    ) -> tuple[Event, ...]:
        return sdk.events(run_id, after, limit)

    @app.get("/api/runs/{run_id}/agents")
    def agents(run_id: UUID) -> tuple[ActorProjection, ...]:
        return sdk.snapshot(run_id).actors

    @app.get("/api/runs/{run_id}/tasks")
    def tasks(run_id: UUID) -> tuple[Task, ...]:
        state = sdk.snapshot(run_id)
        return state.plan.tasks if state.plan else ()

    @app.get("/api/runs/{run_id}/acceptance")
    def acceptance(run_id: UUID) -> AcceptanceView:
        state = sdk.snapshot(run_id)
        return AcceptanceView(
            criteria=state.goal.criteria if state.goal else (), evidence=state.evidence
        )

    @app.get("/api/runs/{run_id}/metrics")
    def metrics(run_id: UUID) -> RunMetrics:
        state = sdk.snapshot(run_id)
        return RunMetrics(
            timing=state.timing,
            task_counts=state.task_counts,
            plan_completion=state.plan_completion,
            server_time=state.server_time,
        )

    @app.post("/api/runs/{run_id}/recover")
    def recover(run_id: UUID, command: RecoveryRequest) -> Task:
        return sdk.orchestrator.recover_task(
            run_id,
            command.execution_id,
            command.reason,
            command.idempotency_key,
            acknowledge_uncertainty=command.acknowledge_uncertainty,
        )

    @app.post("/api/runs/{run_id}/cancel")
    def cancel(run_id: UUID, command: CommandRequest) -> Run:
        return sdk.cancel(run_id, command.idempotency_key)

    @app.post("/api/runs/{run_id}/pause")
    def pause(run_id: UUID, command: CommandRequest) -> Run:
        return sdk.pause(run_id, command.idempotency_key)

    @app.post("/api/runs/{run_id}/resume")
    def resume(run_id: UUID, command: CommandRequest) -> Run:
        return sdk.resume(run_id, command.idempotency_key)

    @app.websocket("/ws/runs/{run_id}")
    async def stream(websocket: WebSocket, run_id: UUID, after: int = 0) -> None:
        if (
            not loopback_client(websocket.client.host if websocket.client else None)
            or after < 0
            or not origin_allowed(websocket.headers.get("origin"), str(websocket.url))
        ):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        cursor = after
        try:
            while True:
                state = await asyncio.to_thread(sdk.snapshot, run_id)
                if cursor > state.last_event_sequence:
                    await websocket.close(code=1008, reason="Invalid event cursor")
                    return
                pending = await asyncio.to_thread(sdk.events, run_id, cursor)
                # Bound the event batch by this snapshot's cursor; newer commits follow next tick.
                batch = [
                    event.model_dump(mode="json")
                    for event in pending
                    if event.sequence <= state.last_event_sequence
                ]
                if batch:
                    await websocket.send_json({"type": "events", "events": batch})
                await websocket.send_json(
                    {"type": "snapshot", "snapshot": state.model_dump(mode="json")}
                )
                cursor = state.last_event_sequence
                await asyncio.sleep(1)
        except WebSocketDisconnect:
            return
        except OrqalisError:
            await websocket.close(code=1008, reason="Run unavailable")
        except SQLAlchemyError:
            await websocket.close(code=1011, reason="Runtime temporarily unavailable")

    frontend = frontend_directory()
    if frontend:
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/runs/{run_id}", include_in_schema=False)
    def index(run_id: str | None = None) -> Response:
        if frontend:
            return FileResponse(frontend / "index.html")
        return JSONResponse(
            {
                "message": (
                    "Frontend assets are missing; reinstall Orqalis or rebuild the contributor UI."
                )
            },
            status_code=503,
        )

    return app
