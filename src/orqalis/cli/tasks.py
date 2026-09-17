"""Project-local Task Capsule history commands."""

import json
from pathlib import Path
from typing import Annotated

import typer

from orqalis.cli.dependencies import command_errors
from orqalis.persistence.filesystem import resolve_project_root
from orqalis.tasks.history import TaskHistoryService

task_app = typer.Typer(no_args_is_help=True, help="Inspect one Task Capsule.")


def tasks(
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
    limit: Annotated[int, typer.Option(min=1, max=10_000)] = 100,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List project-local Task Capsules."""

    with command_errors():
        entries = TaskHistoryService(resolve_project_root(repo)).list(limit)
        if json_output:
            typer.echo(json.dumps([item.model_dump(mode="json") for item in entries]))
            return
        for item in entries:
            typer.echo(f"{item.id} {item.status} {item.title}")


@task_app.command("show")
def show_task(
    task_id: str,
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show a validated Task Capsule by its ORQ identifier."""

    with command_errors():
        view = TaskHistoryService(resolve_project_root(repo)).get(task_id)
        if json_output:
            typer.echo(view.model_dump_json())
            return
        typer.echo(f"{view.task.id}: {view.task.status} - {view.task.title}")
        typer.echo(f"Request: {view.request}")
        typer.echo(f"Events: {view.event_count}")
        if view.summary:
            typer.echo(view.summary.rstrip())


__all__ = ["task_app", "tasks"]
