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


@app.command("impact")
def impact(
    node_or_path: str,
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
    depth: Annotated[int, typer.Option(min=1, max=20)] = 3,
    limit: Annotated[int, typer.Option(min=1, max=1000)] = 100,
    extracted_only: bool = typer.Option(False, "--extracted-only"),
) -> None:
    """Show bounded incoming change-impact candidates as evidence-bearing JSON."""
    with sdk_service(repo) as sdk:
        typer.echo(
            sdk.graph_impact(
                node_or_path,
                max_depth=depth,
                max_nodes=limit,
                include_inferred=not extracted_only,
            ).model_dump_json()
        )


@app.command("path")
def graph_path(
    source_id: str,
    target_id: str,
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
    depth: Annotated[int, typer.Option(min=1, max=20)] = 8,
    limit: Annotated[int, typer.Option(min=1, max=1000)] = 1000,
    extracted_only: bool = typer.Option(False, "--extracted-only"),
) -> None:
    """Explain a directed shortest path between exact graph node IDs as JSON."""
    with sdk_service(repo) as sdk:
        typer.echo(
            sdk.graph_path(
                source_id,
                target_id,
                max_depth=depth,
                max_nodes=limit,
                include_inferred=not extracted_only,
            ).model_dump_json()
        )


@app.command("discover")
def discover(
    query: str,
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
    limit: Annotated[int, typer.Option(min=1, max=100)] = 10,
    max_chars: Annotated[int, typer.Option("--max-chars", min=1000, max=200000)] = 6000,
) -> None:
    """Return bounded memory previews and reference IDs without full bodies."""
    with sdk_service(repo) as sdk:
        typer.echo(sdk.discover_project_memory(query, limit, max_chars).model_dump_json())


@app.command("get")
def get_memory(
    record_id: str,
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
    offset: Annotated[int, typer.Option(min=0)] = 0,
    max_chars: Annotated[int, typer.Option("--max-chars", min=1000, max=200000)] = 10000,
) -> None:
    """Read a bounded body page, including provenance and historical lifecycle state."""
    with sdk_service(repo) as sdk:
        typer.echo(sdk.get_project_memory(record_id, offset, max_chars).model_dump_json())


@app.command("check")
def check_memory(repo: Annotated[Path | None, typer.Option("--repo")] = None) -> None:
    """Check canonical records, lifecycle transitions, and explicit references."""
    with sdk_service(repo) as sdk:
        result = sdk.check_project_memory()
        typer.echo(result.model_dump_json())
        if not result.ok:
            raise typer.Exit(1)


@app.command("proposals")
def proposals(repo: Annotated[Path | None, typer.Option("--repo")] = None) -> None:
    """List reviewable memory proposal IDs and statuses."""
    with sdk_service(repo) as sdk:
        typer.echo(
            json.dumps(
                [
                    {
                        "id": item.id,
                        "status": item.status,
                        "title": item.record.title,
                        "supersedes": item.record.supersedes,
                    }
                    for item in sdk.project_memory_proposals()
                ]
            )
        )


@app.command("proposal")
def proposal(
    proposal_id: str,
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
) -> None:
    """Inspect the proposed body, rationale, evidence, and predecessor digest."""
    with sdk_service(repo) as sdk:
        typer.echo(sdk.project_memory_proposal(proposal_id).model_dump_json())


@app.command("approve")
def approve(
    proposal_id: str,
    reason: Annotated[str, typer.Option("--reason")],
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
) -> None:
    """Approve an inspected memory proposal as the operator."""
    with sdk_service(repo) as sdk:
        typer.echo(
            sdk.review_project_memory(proposal_id, approved=True, reason=reason).model_dump_json()
        )


@app.command("reject")
def reject(
    proposal_id: str,
    reason: Annotated[str, typer.Option("--reason")],
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
) -> None:
    """Reject a memory proposal without changing active knowledge."""
    with sdk_service(repo) as sdk:
        typer.echo(
            sdk.review_project_memory(proposal_id, approved=False, reason=reason).model_dump_json()
        )
