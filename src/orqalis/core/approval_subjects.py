"""Stable approval subjects; mutable runtime status cannot invalidate a decision."""

from orqalis.core.approvals import fingerprint_subject
from orqalis.core.planning import plan_identity
from orqalis.domain.acceptance import GoalContract
from orqalis.domain.delivery import DeliveryPolicy
from orqalis.domain.execution import ExecutionPolicy, ReviewRecord
from orqalis.domain.plan import TaskPlan
from orqalis.domain.run import Run
from orqalis.domain.task import Task


def _digest(value: object) -> str:
    return fingerprint_subject(value)


def goal_subject(contract: GoalContract) -> str:
    return _digest(
        (
            contract.goal.model_dump(mode="json"),
            tuple(
                criterion.model_dump(
                    mode="json",
                    exclude={"status", "attempt_count", "last_validated_at", "evidence_refs"},
                )
                for criterion in contract.criteria
            ),
        )
    )


def plan_subject(plan: TaskPlan) -> str:
    return _digest(plan_identity(plan))


def requirements_task_subject(task: Task) -> str:
    """The preparatory requirements task has no execution workspace yet."""
    return _digest(
        task.model_dump(
            mode="json",
            exclude={"status", "ready_at", "started_at", "completed_at", "attempt_count"},
        )
    )


def task_subject(task: Task, policy: ExecutionPolicy) -> str:
    return _digest(
        (
            task.model_dump(
                mode="json",
                exclude={"status", "ready_at", "started_at", "completed_at", "attempt_count"},
            ),
            policy.model_dump(mode="json"),
        )
    )


def repair_subject(review: ReviewRecord) -> str:
    return _digest((str(review.id), review.plan_version, review.result.model_dump(mode="json")))


def delivery_subject(run: Run, review: ReviewRecord, policy: DeliveryPolicy) -> str:
    return _digest(
        (
            str(run.current_goal_version_id),
            run.plan_version,
            str(review.id),
            review.tree_hash,
            policy.model_dump(mode="json"),
        )
    )
