import json
import webbrowser
from pathlib import Path
from typing import Annotated

import typer

from orqalis.cli.dependencies import sdk_service
from orqalis.memory.curated import MemoryFreshness
from orqalis.persistence.filesystem import ProjectLayout

app = typer.Typer(no_args_is_help=True, help="Commit-aware Project Memory.")


@app.command()
def status(
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Inspect approved curated-memory provenance without changing it."""
    with sdk_service(repo) as sdk:
        statuses = sdk.project_memory_status()
        if json_output:
            typer.echo(
                json.dumps([item.model_dump(mode="json") for item in statuses], sort_keys=True)
            )
        else:
            stale = sum(item.freshness == MemoryFreshness.STALE for item in statuses)
            typer.echo(
                f"Curated memory: {len(statuses) - stale} fresh; {stale} stale; "
                f"{len(statuses)} approved"
            )


@app.command()
def refresh(
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
    record: Annotated[list[str] | None, typer.Option("--record")] = None,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Explicitly revalidate stale approved memory at the current Git commit."""
    with sdk_service(repo) as sdk:
        result = sdk.revalidate_project_memory(tuple(record or ()))
        typer.echo(
            result.model_dump_json()
            if json_output
            else (
                f"Revalidated {len(result.revalidated_ids)} records; "
                f"{len(result.stale_ids)} remain stale"
            )
        )


@app.command()
def search(
    query: str,
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
    limit: Annotated[int, typer.Option(min=1, max=100)] = 10,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Search curated durable memory with provenance freshness."""
    with sdk_service(repo) as sdk:
        matches = sdk.search_project_memory(query, limit)
        if json_output:
            typer.echo(
                json.dumps([match.model_dump(mode="json") for match in matches], sort_keys=True)
            )
        else:
            for match in matches:
                typer.echo(
                    f"{match.record.id} {match.record.title} [{match.freshness}]\n"
                    f"{match.record.content}"
                )
            if not matches:
                typer.echo("No matching curated memory. Targeted repository inspection is needed.")


@app.command("graph")
def graph(
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
    open_browser: bool = typer.Option(False, "--open"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Refresh and inspect the deterministic repository graph."""

    with sdk_service(repo) as sdk:
        value = sdk.project_graph()
        assert sdk.project_root is not None
        path = ProjectLayout(sdk.project_root).contained(
            ProjectLayout(sdk.project_root).memory / "graph" / "graph.json"
        )
        if json_output:
            typer.echo(value.model_dump_json())
        else:
            typer.echo(f"{path}: {len(value.nodes)} nodes, {len(value.edges)} edges")
        if open_browser and not webbrowser.open(path.resolve().as_uri()):
            raise typer.BadParameter("No browser accepted the graph file")
