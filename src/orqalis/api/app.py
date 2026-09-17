import asyncio
import secrets
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
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from orqalis import __version__
from orqalis.api.contracts import AcceptanceView, RunMetrics
from orqalis.api.scope import project_scope_id
from orqalis.core.plan_draft import draft_replacement
from orqalis.delivery.inspection import DiffView
from orqalis.domain.acceptance import GoalContract, GoalDraft
from orqalis.domain.approval import (
    ApprovalDecisionKind,
    ApprovalRequest,
    ControlMode,
    ControlPolicy,
)
from orqalis.domain.base import Contract
from orqalis.domain.capabilities import SkillCatalogEntry
from orqalis.domain.errors import ConflictError, OrqalisError, PolicyDeniedError
from orqalis.domain.events import Event
from orqalis.domain.memory import ContextPack, ProjectBrain
from orqalis.domain.plan import TaskPlan
from orqalis.domain.project import Project
from orqalis.domain.projections import ActorProjection, RunSnapshot
from orqalis.domain.run import Run
from orqalis.domain.task import Task
from orqalis.domain.telemetry import TimelineSegment
from orqalis.memory.curated import MemoryRecordStatus
from orqalis.sdk import Orqalis
from orqalis.security.redaction import safe_diagnostic
from orqalis.tasks import TaskCapsuleView, TaskHistoryEntry

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
    mode: ControlMode = ControlMode.AUTONOMOUS


class PlanCommand(Contract):
    idempotency_key: str = Field(min_length=1, max_length=200)


class PlanReplacement(Contract):
    plan: TaskPlan
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=200)


class GoalRevision(Contract):
    goal: GoalDraft
    reason: str = Field(min_length=1, max_length=1000)
    expected_version: int = Field(ge=1)


class ApprovalDecisionCommand(Contract):
    decision: ApprovalDecisionKind
    expected_subject_digest: str
    reason: str = Field(default="", max_length=1000)


class ControlView(Contract):
    policy: ControlPolicy
    approvals: tuple[ApprovalRequest, ...]


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


def create_app(client: Orqalis | None = None, *, root: Path | None = None) -> FastAPI:
    owns_client = client is None
    sdk = client or Orqalis(root=root)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if owns_client:
            sdk.close()

    app = FastAPI(title="Orqalis Local API", version=__version__, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])

    def require_operator(request: Request) -> str:
        configured = sdk.settings.operator_token
        supplied = request.headers.get("x-orqalis-operator-token", "")
        if (
            configured is None
            or not configured.get_secret_value()
            or not supplied
            or not secrets.compare_digest(supplied, configured.get_secret_value())
        ):
            raise PolicyDeniedError("Operator token is required for approval and edits")
        return "local-ui-operator"

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

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            {"code": "invalid_request", "message": "Request does not match the API contract"},
            status_code=422,
        )

    @app.get("/health")
    def health() -> dict[str, str | None]:
        return {
            "service": "orqalis",
            "version": __version__,
            "project_scope": project_scope_id(sdk.project_root),
        }

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
    ) -> tuple[MemoryRecordStatus, ...]:
        sdk.get_project(project_id)
        return sdk.search_project_memory(query, limit)

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

    @app.get("/api/tasks")
    def task_history(
        limit: Annotated[int, Query(ge=1, le=10_000)] = 100,
    ) -> tuple[TaskHistoryEntry, ...]:
        """List project-local Task Capsules through the application service."""

        history = sdk.task_history
        if history is None:
            raise ConflictError("Task history requires a root-bound filesystem project")
        return history.list(limit)

    @app.get("/api/tasks/{task_id}")
    def task_capsule(task_id: str) -> TaskCapsuleView:
        """Read a historical Task Capsule without exposing raw filesystem access."""

        history = sdk.task_history
        if history is None:
            raise ConflictError("Task history requires a root-bound filesystem project")
        return history.get(task_id)

    @app.post("/api/runs")
    def start(command: StartRequest) -> RunSnapshot:
        return sdk.prepare_run(
            command.project_id, command.request, command.branch, command.goal, command.mode
        )

    @app.get("/api/runs/{run_id}")
    def snapshot(run_id: UUID) -> RunSnapshot:
        return sdk.snapshot(run_id)

    @app.get("/api/runs/{run_id}/controls")
    def controls(run_id: UUID) -> ControlView:
        return ControlView(
            policy=sdk.approvals.policy(run_id),
            approvals=sdk.approvals.list(run_id),
        )

    @app.post("/api/runs/{run_id}/plan/preview")
    def preview_plan(run_id: UUID, command: PlanCommand, request: Request) -> TaskPlan:
        require_operator(request)
        return sdk.plans.preview(run_id, command.idempotency_key)

    @app.get("/api/runs/{run_id}/plan/draft")
    def draft_plan(run_id: UUID) -> TaskPlan:
        state = sdk.snapshot(run_id)
        if state.plan is None:
            raise PolicyDeniedError("Run does not have a plan to edit")
        return draft_replacement(state.plan)

    @app.post("/api/runs/{run_id}/plan/replan")
    def replan_goal(run_id: UUID, command: PlanCommand, request: Request) -> Run:
        require_operator(request)
        return sdk.replan(run_id, command.idempotency_key)

    @app.post("/api/runs/{run_id}/plan/replace")
    def replace_plan(run_id: UUID, command: PlanReplacement, request: Request) -> TaskPlan:
        require_operator(request)
        if command.plan.run_id != run_id:
            raise PolicyDeniedError("Plan belongs to another run")
        return sdk.plans.replace(command.plan, command.expected_version, command.idempotency_key)

    @app.post("/api/runs/{run_id}/goal/revise")
    def revise_goal(run_id: UUID, command: GoalRevision, request: Request) -> GoalContract:
        require_operator(request)
        return sdk.goals.revise(run_id, command.goal, command.reason, command.expected_version)

    @app.post("/api/runs/{run_id}/approvals/{approval_id}/decision")
    def decide_approval(
        run_id: UUID,
        approval_id: UUID,
        command: ApprovalDecisionCommand,
        request: Request,
    ) -> ApprovalRequest:
        actor = require_operator(request)
        return sdk.approvals.decide(
            run_id,
            approval_id,
            command.decision,
            actor,
            command.expected_subject_digest,
            command.reason,
        )

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
            # Subscribe before replaying the durable stream so a commit cannot fall
            # between historical replay and the live subscription.
            async with sdk.event_bus.subscribe(run_id) as subscription:
                while True:
                    state = await asyncio.to_thread(sdk.snapshot, run_id)
                    if cursor > state.last_event_sequence:
                        await websocket.close(code=1008, reason="Invalid event cursor")
                        return
                    pending = await asyncio.to_thread(sdk.events, run_id, cursor)
                    # Bound the batch by this snapshot; a concurrent commit wakes the
                    # subscription and is loaded from the authoritative JSONL stream.
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
                    try:
                        notification = await subscription.receive(timeout=1.0)
                    except TimeoutError:
                        continue
                    if notification.sequence <= cursor:
                        continue
        except WebSocketDisconnect:
            return
        except OrqalisError:
            await websocket.close(code=1008, reason="Run unavailable")

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
