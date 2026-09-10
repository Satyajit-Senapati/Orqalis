from orqalis.core.ports import ProjectUnitOfWork
from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.run import Run, RunState


def guard_delivery(uow: ProjectUnitOfWork, run: Run, target: RunState) -> None:
    if target == RunState.COMPLETED:
        promoted = uow.events.by_key(run.id, "curation:promoted")
        if not promoted or not promoted.payload.memory_ids:
            raise PolicyDeniedError("Durable memory curation is required before completion")
        plan = uow.runtime.get_plan(run.id, run.plan_version)
        if not plan or any(t.status not in {"SUCCEEDED", "SKIPPED"} for t in plan.tasks):
            raise PolicyDeniedError("All tasks must reach successful completion")

    if target not in {
        RunState.CHANGE_GUARD,
        RunState.DOCUMENTING,
        RunState.DELIVERY_VALIDATION,
        RunState.COMMITTING,
        RunState.PUSHING,
        RunState.MEMORY_FINALIZATION,
        RunState.COMPLETED,
    }:
        return
    reviews = uow.execution.reviews(run.id)
    if (
        not reviews
        or reviews[-1].result.overall != "PASS"
        or reviews[-1].goal_version_id != run.current_goal_version_id
    ):
        raise PolicyDeniedError("An independent passing review of the current goal is required")
    if target == RunState.CHANGE_GUARD:
        return
    reports = uow.delivery.guardians(run.id)
    implementation = [r for r in reports if r.checkpoint == "implementation"]
    if (
        not implementation
        or not implementation[-1].passed
        or implementation[-1].tree_hash != reviews[-1].tree_hash
    ):
        raise PolicyDeniedError("Change Guardian must certify the accepted implementation")
    if target == RunState.DOCUMENTING:
        return
    if not any(a.type == "documentation" for a in uow.delivery.artifacts(run.id)):
        raise PolicyDeniedError("Accepted changes must be documented")
    if target == RunState.DELIVERY_VALIDATION:
        return
    validations = uow.delivery.validations(run.id)
    final = [r for r in reports if r.checkpoint == "final"]
    if (
        not validations
        or not validations[-1].passed
        or validations[-1].goal_version_id != run.current_goal_version_id
        or not final
        or not final[-1].passed
        or final[-1].tree_hash != validations[-1].tree_hash
    ):
        raise PolicyDeniedError("Final validation and Guardian must certify the same tree")
    if target == RunState.COMMITTING:
        return
    delivery = uow.delivery.get(run.id)
    if (
        delivery is None
        or not delivery.commit_attached
        or not delivery.commit_sha
        or delivery.tree_hash != final[-1].tree_hash
    ):
        raise PolicyDeniedError("An attached, traceable accepted commit is required")
    if target == RunState.PUSHING and not delivery.policy.push:
        raise PolicyDeniedError("Push was not authorized")
    if target in {RunState.MEMORY_FINALIZATION, RunState.COMPLETED} and (
        delivery.policy.push and delivery.push_status != "pushed"
    ):
        raise PolicyDeniedError("Authorized push has not completed")
