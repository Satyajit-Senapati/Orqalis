import hashlib
from collections.abc import Callable
from uuid import UUID, uuid5

from orqalis.agents.roles import effective_tools
from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit, locked_run
from orqalis.delivery.inspection import ChangeInspectionService
from orqalis.domain.agent import AgentRole
from orqalis.domain.base import utc_now
from orqalis.domain.capabilities import ToolName
from orqalis.domain.errors import ConflictError, NotFoundError, OrqalisError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.execution import RunWorkspace, ToolInvocation
from orqalis.domain.provider import InvocationStatus, ProviderToolCall, ToolObservation
from orqalis.domain.run import RunState
from orqalis.domain.task import TaskStatus
from orqalis.execution.commands import CommandRunner
from orqalis.execution.filesystem import ScopedFilesystem
from orqalis.execution.tool_definitions import ReadDiff, ReadFile, RunCommand, WriteFile
from orqalis.execution.workspaces import verify_workspace
from orqalis.git.service import LocalGitService
from orqalis.observability.instrumentation import observed


class ToolService:
    def __init__(self, factory: Callable[[], ProjectUnitOfWork], git: LocalGitService) -> None:
        self.factory, self.git = factory, git

    @observed("tool.execute")
    def execute(self, provider_invocation_id: UUID, call: ProviderToolCall) -> ToolObservation:
        invocation_id = uuid5(provider_invocation_id, call.id)
        fingerprint = hashlib.sha256(call.model_dump_json().encode()).hexdigest()
        with self.factory() as uow:
            provider = uow.providers.get(provider_invocation_id)
            if (
                provider is None
                or provider.status != InvocationStatus.SUCCEEDED
                or not provider.result
            ):
                raise NotFoundError("Successful provider tool request not found")
            run = locked_run(uow, provider.run_id)
            if call not in provider.result.tool_calls:
                raise PolicyDeniedError("Tool call does not match the persisted provider result")
            existing = uow.execution.tool(invocation_id)
            if existing:
                if existing.request_hash != fingerprint:
                    raise ConflictError("Tool call identity was reused with different arguments")
                if existing.observation:
                    return existing.observation
                raise ConflictError("Tool outcome is uncertain; automatic replay is denied")
            attempt = next(
                item
                for item in uow.runtime.executions(run.id)
                if item.id == provider.task_execution_id
            )
            actor = next(
                item for item in uow.runtime.actors(run.id) if item.id == provider.actor_session_id
            )
            project = uow.projects.get(run.project_id)
            workspace = uow.execution.workspace(run.id)
            if project is None or workspace is None or actor.role is None:
                raise NotFoundError("Worker policy or workspace is missing")
            if attempt.status != TaskStatus.RUNNING or run.state not in {
                RunState.EXECUTING,
                RunState.TESTING,
                RunState.REVIEWING,
                RunState.CHANGE_GUARD,
                RunState.DOCUMENTING,
            }:
                raise ConflictError("Tool execution requires an active task")
            if call.name.value not in actor.allowed_tools or call.name not in effective_tools(
                actor.role, project.settings.permissions
            ):
                raise PolicyDeniedError("Tool denied by current role/project policy")
            if sum(
                item.task_execution_id == attempt.id for item in uow.execution.tools(run.id)
            ) >= (workspace.policy.max_tool_calls):
                raise PolicyDeniedError("Task tool-call budget exhausted")
            verify_workspace(workspace, self.git)
            at = utc_now()
            invocation = ToolInvocation(
                id=invocation_id,
                run_id=run.id,
                task_execution_id=attempt.id,
                actor_session_id=actor.id,
                provider_invocation_id=provider.id,
                call_id=call.id,
                tool=call.name,
                request_hash=fingerprint,
                started_at=at,
                created_at=at,
            )
            uow.execution.save_tool(invocation)
            emit(
                uow,
                run,
                EventType.TOOL_STARTED,
                f"tool:{invocation.id}:start",
                at,
                EventPayload(tool_invocation_id=invocation.id, status="RUNNING"),
                actor.id,
                attempt.task_id,
                attempt.id,
            )
            uow.commit()
        try:
            observation = self._dispatch(
                workspace, call, read_only=actor.role in {AgentRole.REVIEWER, AgentRole.REPAIR}
            )
        except (OrqalisError, OSError, ValueError) as error:
            observation = ToolObservation(
                call_id=call.id,
                tool=call.name,
                succeeded=False,
                summary=(
                    "Tool denied or failed: "
                    + (error.code if isinstance(error, OrqalisError) else "invalid_operation")
                ),
            )
        with self.factory() as uow:
            run = locked_run(uow, invocation.run_id)
            updated = invocation.model_copy(
                update={
                    "completed_at": utc_now(),
                    "observation": observation,
                    "status": "SUCCEEDED" if observation.succeeded else "FAILED",
                }
            )
            uow.execution.save_tool(updated)
            emit(
                uow,
                run,
                EventType.TOOL_COMPLETED,
                f"tool:{invocation.id}:finish",
                updated.completed_at or utc_now(),
                EventPayload(tool_invocation_id=invocation.id, status=updated.status),
                invocation.actor_session_id,
                execution_id=invocation.task_execution_id,
            )
            uow.commit()
        return observation

    def _dispatch(
        self, workspace: RunWorkspace, call: ProviderToolCall, *, read_only: bool = False
    ) -> ToolObservation:
        files = ScopedFilesystem(workspace.path, workspace.policy)
        succeeded = True
        if call.name == ToolName.FILE_READ:
            read = ReadFile.model_validate(call.arguments)
            lines = files.read(read.path).splitlines()
            content = "\n".join(
                f"{index + 1}: {line}"
                for index, line in enumerate(lines)
                if read.start_line <= index + 1 < read.start_line + read.line_count
            )
            summary = content[:15_800] + ("\n[Output truncated]" if len(content) > 15_800 else "")
        elif call.name == ToolName.FILE_WRITE:
            write = WriteFile.model_validate(call.arguments)
            digest = files.write(write.path, write.content)
            summary = f"Wrote {write.path}; sha256={digest}"
        elif call.name == ToolName.TEST_RUN:
            request = RunCommand.model_validate(call.arguments)
            command = next(
                (item for item in workspace.policy.commands if item.id == request.command_id), None
            )
            if command is None:
                raise PolicyDeniedError("Unknown approved command")
            result = CommandRunner(workspace.path, workspace.policy, read_only=read_only).run(
                command
            )
            succeeded, summary = result.passed, result.model_dump_json()[:16_000]
        elif call.name == ToolName.GIT_DIFF:
            diff = ReadDiff.model_validate(call.arguments)
            files.target(diff.path)
            summary = (
                ChangeInspectionService(self.factory, self.git)
                .diff(workspace.run_id, diff.path)
                .diff[:16_000]
            )
        else:
            raise PolicyDeniedError("Tool implementation is unavailable")
        return ToolObservation(
            call_id=call.id, tool=call.name, succeeded=succeeded, summary=summary
        )
