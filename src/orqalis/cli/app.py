import asyncio
import json
import shutil
from contextlib import ExitStack
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

import typer
from pydantic import ValidationError

from orqalis import __version__
from orqalis.api.hosting import local_url, ui_session
from orqalis.cli.catalog import agents, config_app, discover_skills, skills
from orqalis.cli.control import approvals_app, plan_app
from orqalis.cli.dependencies import (
    command_errors,
    sdk_service,
)
from orqalis.cli.goals import app as goals_app
from orqalis.cli.memory import app as memory_app
from orqalis.cli.runs import app as runs_app
from orqalis.cli.tasks import task_app
from orqalis.cli.tasks import tasks as list_tasks
from orqalis.config.settings import Settings
from orqalis.diagnostics import diagnose_project
from orqalis.domain.acceptance import GoalDraft
from orqalis.domain.approval import ApprovalStage, ControlMode
from orqalis.domain.delivery import DeliveryPolicy
from orqalis.domain.execution import ExecutionPolicy
from orqalis.observability.logging import configure_logging
from orqalis.persistence.filesystem import resolve_project_root
from orqalis.providers.configuration import configured_providers

DEFAULT_WORKSPACES = Path.home()

app = typer.Typer(
    no_args_is_help=True, help="Orqalis engineering orchestration and project memory."
)


app.add_typer(memory_app, name="memory")
app.add_typer(goals_app, name="goal")
app.add_typer(runs_app, name="runs")
app.add_typer(task_app, name="task")
app.add_typer(approvals_app, name="approvals")
app.add_typer(plan_app, name="plan")
app.add_typer(config_app, name="config")
app.command("agents")(agents)
app.command("skills")(skills)
app.command("tasks")(list_tasks)


def version_option(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=version_option, is_eager=True, help="Print version and exit."
        ),
    ] = False,
) -> None:
    configure_logging()
    try:
        telemetry_console = Settings().telemetry_console
    except ValidationError:
        typer.echo(
            "Invalid Orqalis configuration; check documented environment variables.", err=True
        )
        raise typer.Exit(2) from None
    if telemetry_console:
        from orqalis.observability.instrumentation import enable_console_telemetry

        enable_console_telemetry()


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


@app.command("modes")
def modes(json_output: bool = typer.Option(False, "--json")) -> None:
    """Describe run control modes and the default supervised gates."""
    values = {
        "autonomous": {"gates": [], "description": "Execute within accepted policies."},
        "supervised": {
            "gates": ["GOAL", "PLAN", "REPAIR", "DELIVERY"],
            "description": "Pause at durable human approval checkpoints.",
        },
    }
    if json_output:
        typer.echo(json.dumps(values, sort_keys=True))
    else:
        for name, value in values.items():
            typer.echo(f"{name}: {value['description']}")
            typer.echo(f"  default gates: {', '.join(value['gates']) or 'none'}")


@app.command("update")
def update_installed_package() -> None:
    """Check or install updates through the globally installed npm launcher."""
    typer.echo(
        "The update command requires the globally installed npm launcher; "
        "install with npm install -g orqalis.",
        err=True,
    )
    raise typer.Exit(2)


@app.command()
def doctor(
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Validate Git and the selected project-local filesystem store."""
    git_ok = shutil.which("git") is not None
    report = diagnose_project(repo)
    if json_output:
        typer.echo(
            json.dumps(
                {"git": git_ok, "project_store": report.model_dump(mode="json")},
                sort_keys=True,
            )
        )
    else:
        typer.echo(f"git: {'OK' if git_ok else 'UNAVAILABLE'}")
        for check in report.checks:
            typer.echo(f"{check.name}: {check.status} - {check.message}")
    if not git_ok or not report.healthy:
        raise typer.Exit(1)


@app.command("init")
def initialize(
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Register the current committed Git repository idempotently."""
    target = resolve_project_root(repo)
    with sdk_service(target) as sdk:
        project = sdk.initialize(target)
        typer.echo(
            project.model_dump_json()
            if json_output
            else f"Initialized {project.name} ({project.id}) on {project.default_branch}"
        )


@app.command()
def status(
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show persisted project identity and current repository state."""
    target = resolve_project_root(repo)
    with sdk_service(target) as sdk:
        project, git_status = sdk.projects.status(target)
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "project": project.model_dump(mode="json"),
                        "git": git_status.model_dump(mode="json"),
                    },
                    sort_keys=True,
                )
            )
        else:
            typer.echo(f"{project.name}: {git_status.branch or 'DETACHED'} @ {git_status.head}")
            typer.echo(f"Changed paths: {len(git_status.changed_paths)}")


@app.command()
def context(
    task: str,
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
    max_chars: Annotated[int | None, typer.Option("--max-chars", min=1000)] = None,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Build a selective graph, memory, task-history, and Git Context Pack."""
    with sdk_service(repo) as sdk:
        pack = sdk.project_context(task, max_chars)
        if json_output:
            typer.echo(pack.model_dump_json())
        else:
            typer.echo(f"Context: {pack.size_chars}/{pack.max_chars} characters")
            typer.echo(f"Relevant files: {len(pack.relevant_files)}")
            typer.echo(f"Graph items: {len(pack.graph)}; memory: {len(pack.memory)}")
            typer.echo(f"Related tasks: {len(pack.related_tasks)}")


@app.command("rebuild-index")
def rebuild_index(
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Rebuild all disposable graph and lexical index artifacts."""

    with sdk_service(repo) as sdk:
        result = sdk.rebuild_project_index()
        if json_output:
            typer.echo(result.model_dump_json())
        else:
            metrics = result.metrics
            typer.echo(
                f"Indexed {metrics.documents_indexed} documents; "
                f"processed {metrics.graph_processed_files} repository files in "
                f"{metrics.duration_ms:.1f}ms"
            )


@app.command()
def serve() -> None:
    """Host the loopback-only API, event feed and packaged UI."""
    import uvicorn

    from orqalis.api.app import create_app

    with command_errors():
        settings = Settings()
        local_url(settings)
        uvicorn.run(create_app(root=settings.project_root), host=settings.host, port=settings.port)


@app.command()
def ui(open_browser: bool = typer.Option(False, "--open")) -> None:
    """Host Mission Control in this terminal until Ctrl+C."""
    with command_errors(), ui_session(Settings(), "/" if open_browser else None) as host:
        typer.echo(host.url)
        if host.owned:
            typer.echo("Mission Control is running; press Ctrl+C to stop it.", err=True)
            host.wait()


@app.command("run")
def prepare_run(
    request: str,
    contract: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    branch: Annotated[str | None, typer.Option()] = None,
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
    open_browser: bool = typer.Option(False, "--open"),
    json_output: bool = typer.Option(False, "--json"),
    policy: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    provider: str = "openai",
    workspaces: Path = DEFAULT_WORKSPACES / ".orqalis" / "workspaces",
    mode: Annotated[str, typer.Option("--mode")] = "autonomous",
    gate: Annotated[list[str] | None, typer.Option("--gate")] = None,
) -> None:
    """Prepare an observable goal with optional supervised stage gates."""
    try:
        selected_mode = ControlMode(mode.upper())
        selected_gates = frozenset(ApprovalStage(item.upper()) for item in gate) if gate else None
    except ValueError as exc:
        raise typer.BadParameter("Invalid mode or gate; see orqalis run --help") from exc
    if selected_gates and selected_mode == ControlMode.AUTONOMOUS:
        raise typer.BadParameter("Custom gates require supervised mode")
    target = resolve_project_root(repo)
    ui_settings = Settings(project_root=target)
    with sdk_service(target) as sdk, ExitStack() as ui_stack:
        project, _ = sdk.projects.status(target)
        state = sdk.prepare_run(
            project.id,
            request,
            branch or f"orqalis/run-{uuid4().hex[:10]}",
            GoalDraft.model_validate_json(contract.read_text(encoding="utf-8"))
            if contract
            else None,
            selected_mode,
            selected_gates,
        )
        host = (
            ui_stack.enter_context(ui_session(ui_settings, f"/runs/{state.run.id}"))
            if open_browser
            else None
        )
        if not json_output:
            typer.echo(f"Run {state.run.id}: {state.run.state}")
            typer.echo(f"{local_url(ui_settings)}/runs/{state.run.id}")
        if contract is None:
            asyncio.run(sdk.requirements().define(state.run.id, provider))
            state = sdk.snapshot(state.run.id)
        if policy is not None:
            asyncio.run(
                sdk.executor(workspaces).execute(
                    state.run.id,
                    provider,
                    ExecutionPolicy.model_validate_json(policy.read_text(encoding="utf-8")),
                )
            )
            state = sdk.snapshot(state.run.id)
        if json_output:
            typer.echo(state.model_dump_json())
        else:
            typer.echo(f"Run {state.run.id}: {state.run.state}")
            typer.echo(f"{local_url(ui_settings)}/runs/{state.run.id}")
        if host is not None and host.owned:
            typer.echo("Mission Control is running; press Ctrl+C to stop it.", err=True)
            host.wait()


@app.command()
def capabilities() -> None:
    """List configured provider availability and discoverable skill metadata."""
    with command_errors():
        settings = Settings()
        typer.echo(
            json.dumps(
                {
                    "providers": [
                        provider.descriptor.model_dump(mode="json")
                        for provider in configured_providers(settings)
                    ],
                    "skills": [
                        skill.model_dump(mode="json") for skill in discover_skills(settings)
                    ],
                },
                indent=2,
            )
        )


@app.command("execute")
def execute_run(
    run_id: UUID,
    policy: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    provider: str = "openai",
    workspaces: Path = DEFAULT_WORKSPACES / ".orqalis" / "workspaces",
) -> None:
    """Execute or continue a prepared run through evidence-backed review."""
    with sdk_service() as sdk:
        result = asyncio.run(
            sdk.executor(workspaces).execute(
                run_id,
                provider,
                ExecutionPolicy.model_validate_json(policy.read_text(encoding="utf-8")),
            )
        )
        typer.echo(result.model_dump_json())


@app.command("finalize")
def finalize_run(
    run_id: UUID,
    policy: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
) -> None:
    """Certify, document and commit an accepted run under an explicit delivery policy."""
    with sdk_service() as sdk:
        result = asyncio.run(
            sdk.delivery.finalize(
                run_id, DeliveryPolicy.model_validate_json(policy.read_text(encoding="utf-8"))
            )
        )
        typer.echo(result.model_dump_json())


@app.command("mcp")
def mcp_server(
    policy: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    root: Annotated[Path | None, typer.Option("--root")] = None,
) -> None:
    """Serve the authorized project over MCP stdio; stdout is reserved for protocol."""
    from orqalis.mcp.policy import MCPPolicy
    from orqalis.mcp.server import create_mcp

    with sdk_service(root) as sdk:
        settings = MCPPolicy.model_validate_json(policy.read_text(encoding="utf-8"))
        sdk.get_project(settings.project_id)
        create_mcp(sdk, settings).run(transport="stdio")


@app.command("define-goal")
def define_goal(run_id: UUID, provider: str = "openai") -> None:
    """Continue a prepared request through its persisted Requirements actor."""
    with sdk_service() as sdk:
        typer.echo(asyncio.run(sdk.requirements().define(run_id, provider)).model_dump_json())
