"""CLI surface for the same persisted operator controls used by Mission Control."""

import getpass
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

import typer

from orqalis.cli.dependencies import sdk_service
from orqalis.core.plan_draft import draft_replacement
from orqalis.domain.approval import ApprovalDecisionKind
from orqalis.domain.errors import ConflictError
from orqalis.domain.plan import TaskPlan

approvals_app = typer.Typer(no_args_is_help=True, help="Inspect and decide operator gates.")
plan_app = typer.Typer(no_args_is_help=True, help="Preview, inspect, and edit the task DAG.")


@approvals_app.command("list")
def list_approvals(run_id: UUID, json_output: bool = typer.Option(False, "--json")) -> None:
    """Show pending and historical decisions with their exact subject fingerprints."""
    with sdk_service() as sdk:
        service = sdk.approvals
        requests = service.list(run_id)
        if json_output:
            typer.echo("[" + ",".join(item.model_dump_json() for item in requests) + "]")
        else:
            policy = service.policy(run_id)
            typer.echo(f"Mode: {policy.mode}; gates: {', '.join(sorted(policy.gates)) or 'none'}")
            for item in requests:
                typer.echo(
                    f"{item.id} {item.stage} v{item.subject_version} {item.status} "
                    f"digest={item.subject_digest} reason={item.reason}"
                )


@approvals_app.command("decide")
def decide_approval(
    run_id: UUID,
    request_id: UUID,
    decision: ApprovalDecisionKind,
    expected_digest: Annotated[str, typer.Option("--expected-digest")],
    reason: str = typer.Option("", "--reason"),
) -> None:
    """Record one human decision for the exact inspected subject digest."""
    with sdk_service() as sdk:
        service = sdk.approvals
        result = service.decide(
            run_id, request_id, decision, getpass.getuser(), expected_digest, reason
        )
        typer.echo(result.model_dump_json())


@approvals_app.command("approve")
def approve(
    run_id: UUID,
    request_id: UUID,
    expected_digest: Annotated[str, typer.Option("--expected-digest")],
    reason: str = typer.Option("", "--reason"),
) -> None:
    """Approve the exact current goal, plan, repair, task, or delivery subject."""
    decide_approval(run_id, request_id, ApprovalDecisionKind.APPROVE, expected_digest, reason)


@approvals_app.command("reject")
def reject(
    run_id: UUID,
    request_id: UUID,
    expected_digest: Annotated[str, typer.Option("--expected-digest")],
    reason: str = typer.Option("", "--reason"),
) -> None:
    """Reject the exact current subject; a revision can create a new request."""
    decide_approval(run_id, request_id, ApprovalDecisionKind.REJECT, expected_digest, reason)


@plan_app.command("preview")
def preview_plan(run_id: UUID) -> None:
    """Create the first durable plan without allocating an execution workspace."""
    with sdk_service() as sdk:
        typer.echo(sdk.plans.preview(run_id, str(uuid4())).model_dump_json())


@plan_app.command("show")
def show_plan(run_id: UUID) -> None:
    """Print the current persisted dependency DAG as JSON."""
    with sdk_service() as sdk:
        state = sdk.snapshot(run_id)
        if state.plan is None:
            raise ConflictError("Run does not have a plan yet")
        typer.echo(state.plan.model_dump_json())


@plan_app.command("draft")
def draft_plan(
    run_id: UUID,
    output: Annotated[Path, typer.Option("--output")],
) -> None:
    """Write a next-version JSON draft with fresh task IDs for editing."""
    with sdk_service() as sdk:
        state = sdk.snapshot(run_id)
        if state.plan is None:
            raise ConflictError("Run does not have a plan yet")
        draft = draft_replacement(state.plan)
        with output.open("x", encoding="utf-8") as stream:
            stream.write(draft.model_dump_json(indent=2) + "\n")
        typer.echo(f"Draft plan v{draft.version} written to {output}")


@plan_app.command("replace")
def replace_plan(
    run_id: UUID,
    file: Annotated[Path, typer.Option("--file", exists=True, dir_okay=False)],
    expected_version: Annotated[int, typer.Option("--expected-version", min=1)],
) -> None:
    """Install an edited, unexecuted DAG while preserving the prior version."""
    draft = TaskPlan.model_validate_json(file.read_text(encoding="utf-8"))
    if draft.run_id != run_id:
        raise ConflictError("Plan belongs to another run")
    with sdk_service() as sdk:
        typer.echo(sdk.plans.replace(draft, expected_version, str(uuid4())).model_dump_json())
