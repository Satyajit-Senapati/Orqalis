import hashlib
from collections.abc import Callable
from uuid import UUID

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit, locked_run, require_key
from orqalis.core.task_runtime import TaskRuntime
from orqalis.domain.agent import AgentRole
from orqalis.domain.base import utc_now
from orqalis.domain.errors import ConflictError, InputError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.provider import InvocationStatus, ProviderErrorCode
from orqalis.domain.run import RunState
from orqalis.domain.task import Task, TaskStatus
from orqalis.security.redaction import safe_diagnostic


class RecoveryService:
    """Explicit, audited replacement attempt after the owner has inspected uncertainty."""

    def __init__(self, factory: Callable[[], ProjectUnitOfWork]) -> None:
        self.factory = factory

    def retry(
        self,
        run_id: UUID,
        execution_id: UUID,
        reason: str,
        key: str,
        *,
        acknowledge_uncertainty: bool = False,
    ) -> Task:
        require_key(key)
        if not acknowledge_uncertainty:
            raise PolicyDeniedError(
                "Confirm prior workers stopped and their effects were inspected before recovery"
            )
        if not reason.strip() or safe_diagnostic(reason) != reason or len(reason) > 2000:
            raise InputError("Recovery requires a concise, non-secret reason")
        fingerprint = hashlib.sha256(f"{execution_id}:{reason}".encode()).hexdigest()
        with self.factory() as lease:
            if not lease.execution.try_run_lock(run_id):
                raise ConflictError("A worker still owns this run; recovery is denied")
            with self.factory() as uow:
                run = locked_run(uow, run_id)
                receipt = uow.events.by_key(run_id, f"recovery:{key}")
                if receipt and receipt.payload.summary != fingerprint:
                    raise ConflictError("Recovery key belongs to a different request")
                plan = uow.runtime.get_plan(run_id, run.plan_version)
                if plan is not None and plan.goal_version_id != run.current_goal_version_id:
                    raise ConflictError("Recovery requires the unchanged goal and plan")
                attempt = next(
                    (a for a in uow.runtime.executions(run_id) if a.id == execution_id), None
                )
                task = next(
                    (t for t in uow.runtime.tasks(run_id) if attempt and t.id == attempt.task_id),
                    None,
                )
                if task is None or attempt is None:
                    raise ConflictError("Recovery attempt is not in this run's current plan")
                if plan is None and not (
                    task.plan_version == 0 and task.preferred_role == AgentRole.REQUIREMENTS
                ):
                    raise ConflictError(
                        "Only preparatory Requirements work can recover without a plan"
                    )
                if receipt:
                    return task
                if run.state in {
                    RunState.COMPLETED,
                    RunState.CANCELLED,
                    RunState.FAILED,
                    RunState.HUMAN_REVIEW_REQUIRED,
                }:
                    raise ConflictError(
                        "Terminal or human-review runs cannot retry worker attempts"
                    )
                if attempt.status not in {
                    TaskStatus.RUNNING,
                    TaskStatus.WAITING,
                    TaskStatus.BLOCKED,
                }:
                    raise ConflictError(
                        "Only an interrupted or blocked active attempt can be replaced"
                    )
                project = uow.projects.get(run.project_id)
                if project is None or task.attempt_count >= project.settings.max_task_attempts:
                    raise PolicyDeniedError(
                        "Task attempt limit reached; human review or a new run is required"
                    )
                if any(
                    a.task_id == task.id and a.attempt > attempt.attempt
                    for a in uow.runtime.executions(run_id)
                ):
                    raise ConflictError("A newer task attempt already exists")
                at = utc_now()
                for provider in uow.providers.list(run_id):
                    if (
                        provider.task_execution_id == execution_id
                        and provider.status == InvocationStatus.RUNNING
                    ):
                        uow.providers.save(
                            provider.model_copy(
                                update={
                                    "status": InvocationStatus.INTERRUPTED,
                                    "completed_at": at,
                                    "error_code": ProviderErrorCode.INTERRUPTED,
                                }
                            )
                        )
                        emit(
                            uow,
                            run,
                            EventType.PROVIDER_INVOCATION_COMPLETED,
                            f"provider:{provider.idempotency_key}:finish",
                            at,
                            EventPayload(provider_execution_id=provider.id, status="INTERRUPTED"),
                            provider.actor_session_id,
                            task.id,
                            attempt.id,
                        )
                for tool in uow.execution.tools(run_id):
                    if tool.task_execution_id == execution_id and tool.status == "RUNNING":
                        uow.execution.save_tool(
                            tool.model_copy(
                                update={
                                    "status": "INTERRUPTED",
                                    "completed_at": at,
                                }
                            )
                        )
                        emit(
                            uow,
                            run,
                            EventType.TOOL_COMPLETED,
                            f"tool:{tool.id}:finish",
                            at,
                            EventPayload(tool_invocation_id=tool.id, status="INTERRUPTED"),
                            tool.actor_session_id,
                            task.id,
                            attempt.id,
                        )
                TaskRuntime(self.factory).transition_in_transaction(
                    uow,
                    run,
                    execution_id,
                    TaskStatus.FAILED,
                    f"recovery:{key}:retire",
                    at,
                )
                ready = task.model_copy(
                    update={
                        "status": TaskStatus.READY,
                        "ready_at": at,
                        "started_at": None,
                        "completed_at": None,
                    }
                )
                uow.runtime.save_task(ready)
                emit(
                    uow,
                    run,
                    EventType.APPROVAL_RECORDED,
                    f"recovery:{key}",
                    at,
                    EventPayload(summary=fingerprint, reason=reason, status="retry_authorized"),
                    task_id=task.id,
                    execution_id=attempt.id,
                )
                emit(
                    uow,
                    run,
                    EventType.TASK_READY,
                    f"recovery:{key}:ready",
                    at,
                    EventPayload(status="READY", reason="Explicit recovery authorized"),
                    task_id=task.id,
                )
                uow.commit()
                return ready
