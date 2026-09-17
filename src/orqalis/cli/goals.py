from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer

from orqalis.cli.dependencies import project_service
from orqalis.core.goals import GoalService
from orqalis.domain.acceptance import CommandValidation, GoalDraft
from orqalis.evaluation.validators import LocalEvaluator
from orqalis.git.service import LocalGitService
from orqalis.persistence.filesystem import resolve_project_root

app = typer.Typer(no_args_is_help=True, help="Versioned goals and evidence-backed acceptance.")


@app.command()
def create(
    request: str,
    contract: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    branch: Annotated[str, typer.Option()],
    repo: Annotated[Path | None, typer.Option("--repo")] = None,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Create a run and goal from an explicit JSON acceptance contract."""
    target = resolve_project_root(repo)
    with project_service(target) as projects:
        project, status = projects.status(target)
        LocalGitService().validate_branch(
            project.repo_root, branch, project.settings.protected_branches
        )
        draft = GoalDraft.model_validate_json(contract.read_text(encoding="utf-8"))
        run, goal = GoalService(projects.unit_of_work).create(
            project, request, branch, status.head, draft
        )
        typer.echo(
            goal.model_dump_json()
            if json_output
            else f"Run {run.id}; goal v{goal.goal.version}; {len(goal.criteria)} criteria"
        )


@app.command()
def show(run_id: UUID, json_output: bool = typer.Option(False, "--json")) -> None:
    """Show the current goal and acceptance evidence references."""
    with project_service() as projects:
        contract = GoalService(projects.unit_of_work).get(run_id)
        if json_output:
            typer.echo(contract.model_dump_json())
        else:
            typer.echo(f"Goal v{contract.goal.version}: {contract.goal.goal}")
            for criterion in contract.criteria:
                typer.echo(f"{criterion.key} {criterion.status}: {criterion.description}")


@app.command()
def revise(
    run_id: UUID,
    contract: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    reason: Annotated[str, typer.Option()],
    expected_version: Annotated[int, typer.Option(min=1)],
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Create an explicit revision; preserve all prior goals and evidence."""
    with project_service() as projects:
        draft = GoalDraft.model_validate_json(contract.read_text(encoding="utf-8"))
        revised = GoalService(projects.unit_of_work).revise(run_id, draft, reason, expected_version)
        typer.echo(
            revised.model_dump_json() if json_output else f"Created goal v{revised.goal.version}"
        )


@app.command()
def validate(
    run_id: UUID,
    criterion_key: str,
    idempotency_key: Annotated[str, typer.Option()],
    workspace: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    allow_configured_commands: bool = typer.Option(False, "--allow-configured-commands"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Run deterministic checks; command execution requires explicit opt-in."""
    with project_service() as projects:
        goals = GoalService(projects.unit_of_work)
        contract = goals.get(run_id)
        commands = (
            frozenset(
                criterion.validation_spec.argv
                for criterion in contract.criteria
                if isinstance(criterion.validation_spec, CommandValidation)
            )
            if allow_configured_commands
            else frozenset()
        )
        evidence = goals.validate(
            run_id, criterion_key, LocalEvaluator(workspace, commands), idempotency_key
        )
        typer.echo(
            evidence.model_dump_json()
            if json_output
            else f"{criterion_key}: {'PASS' if evidence.structured_data.passed else 'NOT PASSED'}"
        )
        if not evidence.structured_data.passed:
            raise typer.Exit(1)
