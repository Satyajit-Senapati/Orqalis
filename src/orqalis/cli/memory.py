import json
from pathlib import Path
from typing import Annotated

import typer

from orqalis.cli.dependencies import memory_service

app = typer.Typer(no_args_is_help=True, help="Commit-aware Project Memory.")


@app.command()
def status(
    repo: Annotated[Path, typer.Option("--repo")] = Path("."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Inspect memory freshness without triggering a rescan."""
    with memory_service(repo) as (project, service):
        health = service.health(project)
        if json_output:
            typer.echo(health.model_dump_json())
        else:
            typer.echo(f"Memory: {'current' if health.fresh else 'needs verification'}")
            typer.echo(f"Indexed: {health.indexed_commit or 'not indexed'}")
            typer.echo(f"Current: {health.current_commit}; active items: {health.active_items}")


@app.command()
def refresh(
    repo: Annotated[Path, typer.Option("--repo")] = Path("."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Refresh only committed paths changed since the last snapshot."""
    with memory_service(repo) as (project, service):
        result = service.refresh(project)
        typer.echo(
            result.model_dump_json()
            if json_output
            else (
                f"Scanned {len(result.scanned_paths)} paths; "
                f"invalidated {result.invalidated_items} items"
            )
        )


@app.command()
def search(
    query: str,
    repo: Annotated[Path, typer.Option("--repo")] = Path("."),
    limit: Annotated[int, typer.Option(min=1, max=100)] = 10,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Search current memory with source provenance."""
    with memory_service(repo) as (project, service):
        matches = service.search(project, query, limit)
        if json_output:
            typer.echo(
                json.dumps([match.model_dump(mode="json") for match in matches], sort_keys=True)
            )
        else:
            for match in matches:
                typer.echo(
                    f"{match.item.title} [{match.item.source_commit[:12]}]\n{match.item.content}"
                )
            if not matches:
                typer.echo("No matching memory. Targeted repository inspection is needed.")
