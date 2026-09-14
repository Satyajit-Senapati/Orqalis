import asyncio
import json
import shutil
from contextlib import ExitStack
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

import typer
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from orqalis import __version__
from orqalis.api.hosting import local_url, ui_session
from orqalis.cli.catalog import agents, config_app, discover_skills, skills
from orqalis.cli.control import approvals_app, plan_app
from orqalis.cli.dependencies import command_errors, memory_service, project_service
from orqalis.cli.goals import app as goals_app
from orqalis.cli.memory import app as memory_app
from orqalis.cli.runs import app as runs_app
from orqalis.config.settings import Settings
from orqalis.domain.acceptance import GoalDraft
from orqalis.domain.approval import ApprovalStage, ControlMode
from orqalis.domain.delivery import DeliveryPolicy
from orqalis.domain.execution import ExecutionPolicy
from orqalis.observability.logging import configure_logging
from orqalis.persistence.database import create_database_engine
from orqalis.providers.configuration import configured_providers
from orqalis.sdk import Orqalis

DEFAULT_WORKSPACES = Path.home()

app = typer.Typer(
    no_args_is_help=True, help="Orqalis engineering orchestration and project memory."
)


app.add_typer(memory_app, name="memory")
app.add_typer(goals_app, name="goal")
app.add_typer(runs_app, name="runs")
app.add_typer(approvals_app, name="approvals")
app.add_typer(plan_app, name="plan")
app.add_typer(config_app, name="config")
app.command("agents")(agents)
app.command("skills")(skills)


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
def migrate() -> None:
    """Upgrade PostgreSQL using installed migrations; no repository checkout required."""
    from alembic.util.exc import CommandError

    from orqalis.persistence.migrate import upgrade_database

    try:
        upgrade_database()
    except (SQLAlchemyError, CommandError):
        typer.echo(
            "Migration failed; check database access and installed schema history.", err=True
        )
        raise typer.Exit(1) from None
    typer.echo("Database upgraded to the installed schema head.")


@app.command()
def doctor(json_output: bool = typer.Option(False, "--json")) -> None:
    """Check Git and PostgreSQL connectivity without mutating the database."""
    engine = create_database_engine(Settings())
    database_ok = False
    try:
        with engine.connect() as connection:
            database_ok = connection.scalar(text("SELECT 1")) == 1
    except SQLAlchemyError:
        pass  # Expected diagnostic failure; do not print connection credentials.
    finally:
        engine.dispose()
    checks = {"git": shutil.which("git") is not None, "postgresql": database_ok}
    if json_output:
        typer.echo(json.dumps(checks, sort_keys=True))
    else:
        for name, passed in checks.items():
            typer.echo(f"{name}: {'OK' if passed else 'UNAVAILABLE'}")
    if not all(checks.values()):
        raise typer.Exit(1)


@app.command("init")
def initialize(
    repo: Annotated[Path, typer.Option("--repo")] = Path("."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Register the current committed Git repository idempotently."""
    with project_service() as service:
        project = Orqalis(unit_of_work=service.unit_of_work).initialize(repo)
        typer.echo(
            project.model_dump_json()
            if json_output
            else f"Initialized {project.name} ({project.id}) on {project.default_branch}"
        )


@app.command()
def status(
    repo: Annotated[Path, typer.Option("--repo")] = Path("."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show persisted project identity and current repository state."""
    with project_service() as service:
        project, git_status = service.status(repo)
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
    repo: Annotated[Path, typer.Option("--repo")] = Path("."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Build a bounded, source-backed Context Pack with freshness and gaps."""
    with memory_service(repo) as (project, service):
        pack = service.context(project, task)
        if json_output:
            typer.echo(pack.model_dump_json())
        else:
            typer.echo(
                f"Context: {len(pack.items)} items; inspection needed: {pack.requires_inspection}"
            )
            for match in pack.items:
                typer.echo(match.item.title)
                typer.echo(match.item.content)


@app.command()
def serve() -> None:
    """Host the loopback-only API, event feed and packaged UI."""
    import uvicorn

    from orqalis.api.app import create_app

    with command_errors():
        settings = Settings()
        local_url(settings)
        uvicorn.run(create_app(), host=settings.host, port=settings.port)


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
    repo: Annotated[Path, typer.Option("--repo")] = Path("."),
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
    with project_service() as projects, ExitStack() as ui_stack:
        project, _ = projects.status(repo)
        sdk = Orqalis(unit_of_work=projects.unit_of_work)
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
            ui_stack.enter_context(ui_session(Settings(), f"/runs/{state.run.id}"))
            if open_browser
            else None
        )
        if not json_output:
            typer.echo(f"Run {state.run.id}: {state.run.state}")
            typer.echo(f"{local_url(Settings())}/runs/{state.run.id}")
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
            typer.echo(f"{local_url(Settings())}/runs/{state.run.id}")
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
    with project_service() as projects:
        sdk = Orqalis(unit_of_work=projects.unit_of_work)
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
    with project_service() as projects:
        sdk = Orqalis(unit_of_work=projects.unit_of_work)
        result = asyncio.run(
            sdk.delivery.finalize(
                run_id, DeliveryPolicy.model_validate_json(policy.read_text(encoding="utf-8"))
            )
        )
        typer.echo(result.model_dump_json())


@app.command("mcp")
def mcp_server(policy: Annotated[Path, typer.Option(exists=True, dir_okay=False)]) -> None:
    """Serve the authorized project over MCP stdio; stdout is reserved for protocol."""
    from orqalis.mcp.policy import MCPPolicy
    from orqalis.mcp.server import create_mcp

    with project_service() as projects:
        sdk = Orqalis(unit_of_work=projects.unit_of_work)
        settings = MCPPolicy.model_validate_json(policy.read_text(encoding="utf-8"))
        sdk.get_project(settings.project_id)
        create_mcp(sdk, settings).run(transport="stdio")


@app.command("define-goal")
def define_goal(run_id: UUID, provider: str = "openai") -> None:
    """Continue a prepared request through its persisted Requirements actor."""
    with project_service() as projects:
        sdk = Orqalis(unit_of_work=projects.unit_of_work)
        typer.echo(asyncio.run(sdk.requirements().define(run_id, provider)).model_dump_json())
