import json
from uuid import UUID, uuid4

import typer

from orqalis.cli.dependencies import sdk_service

app = typer.Typer(invoke_without_command=True, help="Inspect and control persisted runs.")


@app.callback()
def list_runs(ctx: typer.Context, json_output: bool = typer.Option(False, "--json")) -> None:
    if ctx.invoked_subcommand:
        return
    with sdk_service() as sdk:
        runs = sdk.list_runs()
        if json_output:
            typer.echo(json.dumps([run.model_dump(mode="json") for run in runs], sort_keys=True))
        else:
            for run in runs:
                typer.echo(f"{run.id} {run.state} {run.request}")


@app.command()
def show(run_id: UUID, json_output: bool = typer.Option(False, "--json")) -> None:
    """Load a consistent snapshot, including actor/task/phase timing."""
    with sdk_service() as sdk:
        snapshot = sdk.snapshot(run_id)
        if json_output:
            typer.echo(snapshot.model_dump_json())
        else:
            typer.echo(
                f"{run_id}: {snapshot.run.state}; plan completion {snapshot.plan_completion:.0f}%"
            )
            for actor in snapshot.actors:
                typer.echo(
                    f"{actor.session.actor_type} {actor.session.role or 'orchestrator'}: "
                    f"{actor.session.status} {actor.timing.wall_ms / 1000:.1f}s"
                )


@app.command()
def pause(run_id: UUID) -> None:
    """Pause at a quiescent worker checkpoint."""
    with sdk_service() as sdk:
        run = sdk.pause(run_id, str(uuid4()))
        typer.echo(run.model_dump_json())


@app.command()
def resume(run_id: UUID) -> None:
    """Resume the persisted prior state without recreating successful attempts."""
    with sdk_service() as sdk:
        typer.echo(sdk.resume(run_id, str(uuid4())).model_dump_json())


@app.command()
def cancel(run_id: UUID) -> None:
    """Cancel the run and all unfinished task attempts."""
    with sdk_service() as sdk:
        run = sdk.cancel(run_id, str(uuid4()))
        typer.echo(run.model_dump_json())


@app.command()
def recover(
    run_id: UUID,
    execution_id: UUID,
    reason: str = typer.Option(...),
    acknowledge_uncertainty: bool = typer.Option(False, "--acknowledge-uncertainty"),
) -> None:
    """Replace an interrupted attempt after stopping old workers and inspecting their effects."""
    with sdk_service() as sdk:
        task = sdk.orchestrator.recover_task(
            run_id,
            execution_id,
            reason,
            str(uuid4()),
            acknowledge_uncertainty=acknowledge_uncertainty,
        )
        typer.echo(task.model_dump_json())


@app.command()
def replan(run_id: UUID) -> None:
    """Install fresh work for an explicitly revised goal while preserving prior history."""
    with sdk_service() as sdk:
        typer.echo(sdk.replan(run_id).model_dump_json())


@app.command("prepare")
def continue_preparation(run_id: UUID) -> None:
    """Continue interrupted context preparation without creating a new run."""
    with sdk_service() as sdk:
        state = sdk.continue_preparation(run_id)
        typer.echo(state.model_dump_json())
