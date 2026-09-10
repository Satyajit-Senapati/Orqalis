import json
from uuid import UUID, uuid4

import typer

from orqalis.cli.dependencies import project_service
from orqalis.core.orchestrator import Orchestrator
from orqalis.domain.run import RunState
from orqalis.observability.projections import SnapshotProjectionService

app = typer.Typer(invoke_without_command=True, help="Inspect and control persisted runs.")


@app.callback()
def list_runs(ctx: typer.Context, json_output: bool = typer.Option(False, "--json")) -> None:
    if ctx.invoked_subcommand:
        return
    with project_service() as projects, projects.unit_of_work() as uow:
        runs = uow.runs.list()
        if json_output:
            typer.echo(json.dumps([run.model_dump(mode="json") for run in runs], sort_keys=True))
        else:
            for run in runs:
                typer.echo(f"{run.id} {run.state} {run.request}")


@app.command()
def show(run_id: UUID, json_output: bool = typer.Option(False, "--json")) -> None:
    """Load a consistent snapshot, including actor/task/phase timing."""
    with project_service() as projects:
        snapshot = SnapshotProjectionService(projects.unit_of_work).get_snapshot(run_id)
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
    with project_service() as projects:
        run = Orchestrator(projects.unit_of_work).advance(run_id, RunState.PAUSED, str(uuid4()))
        typer.echo(run.model_dump_json())


@app.command()
def resume(run_id: UUID) -> None:
    """Resume the persisted prior state without recreating successful attempts."""
    with project_service() as projects:
        typer.echo(
            Orchestrator(projects.unit_of_work).resume(run_id, str(uuid4())).model_dump_json()
        )


@app.command()
def cancel(run_id: UUID) -> None:
    """Cancel the run and all unfinished task attempts."""
    with project_service() as projects:
        run = Orchestrator(projects.unit_of_work).advance(run_id, RunState.CANCELLED, str(uuid4()))
        typer.echo(run.model_dump_json())


@app.command()
def recover(
    run_id: UUID,
    execution_id: UUID,
    reason: str = typer.Option(...),
    acknowledge_uncertainty: bool = typer.Option(False, "--acknowledge-uncertainty"),
) -> None:
    """Replace an interrupted attempt after stopping old workers and inspecting their effects."""
    with project_service() as projects:
        task = Orchestrator(projects.unit_of_work).recover_task(
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
    from orqalis.sdk import Orqalis

    with project_service() as projects:
        typer.echo(Orqalis(unit_of_work=projects.unit_of_work).replan(run_id).model_dump_json())


@app.command("prepare")
def continue_preparation(run_id: UUID) -> None:
    """Continue interrupted context preparation without creating a new run."""
    from orqalis.sdk import Orqalis

    with project_service() as projects:
        state = Orqalis(unit_of_work=projects.unit_of_work).continue_preparation(run_id)
        typer.echo(state.model_dump_json())
