from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid5

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit, locked_run
from orqalis.delivery.gates import guard_delivery
from orqalis.domain.agent import ActorStatus, AgentRole
from orqalis.domain.base import utc_now
from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.run import RunState
from orqalis.git.service import LocalGitService
from orqalis.memory.curated import CuratedMemoryStore, MemoryProposal
from orqalis.persistence.filesystem import ProjectLayout, TaskCapsuleStore
from orqalis.security.redaction import safe_diagnostic


class MemoryCurator:
    """Stage verified task outcomes under the configured curated-memory policy."""

    def __init__(self, factory: Callable[[], ProjectUnitOfWork], git: LocalGitService) -> None:
        self.factory, self.git = factory, git

    def promote(self, run_id: UUID, actor_id: UUID) -> tuple[UUID, ...]:
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            if run.state != RunState.MEMORY_FINALIZATION:
                raise PolicyDeniedError("Memory promotion requires accepted Git delivery")
            guard_delivery(uow, run, RunState.MEMORY_FINALIZATION)
            actor = next((a for a in uow.runtime.actors(run_id) if a.id == actor_id), None)
            if (
                not actor
                or actor.role != AgentRole.MEMORY_CURATOR
                or actor.status != ActorStatus.WORKING
            ):
                raise PolicyDeniedError("Memory promotion requires an active Memory Curator")
            delivery = uow.delivery.get(run_id)
            workspace = uow.execution.workspace(run_id)
            project = uow.projects.get(run.project_id)
            assert delivery and delivery.commit_sha and workspace and project
            state = self.git.status(workspace.path)
            tree = self.git._execute(workspace.path, ("rev-parse", "HEAD^{tree}")).decode().strip()
            if (
                state.head != delivery.commit_sha
                or state.changed_paths
                or tree != delivery.git_tree_sha
            ):
                raise PolicyDeniedError("Delivered workspace changed before curation")
            replay = uow.events.by_key(run_id, "curation:promoted")
            replayed = replay.payload.memory_ids if replay else None
            goal = (
                uow.runs.get_goal(run.current_goal_version_id)
                if run.current_goal_version_id
                else None
            )
            final = uow.delivery.validations(run_id)[-1]
            assert goal is not None
            content = (
                f"Delivered goal: {goal.goal.goal}\n"
                f"Commit: {delivery.commit_sha}\nRun: {run_id}\n"
                f"Goal version: {goal.goal.version}; required acceptance passed.\n"
                f"Final validation: {final.id}; evidence: "
                + ", ".join(str(ref) for ref in final.evidence_ids)
            )
            if safe_diagnostic(content) != content:
                raise PolicyDeniedError("Unsafe durable run summary")
        proposal = self._stage_outcome(
            project.repo_root,
            run_id,
            delivery.commit_sha,
            content,
            str(final.id),
        )
        if replayed is not None:
            return replayed
        receipt = uuid5(run_id, f"curated-memory:{proposal.record.id}")
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            if run.state != RunState.MEMORY_FINALIZATION:
                raise PolicyDeniedError("Run left its memory curation checkpoint")
            guard_delivery(uow, run, RunState.MEMORY_FINALIZATION)
            replay = uow.events.by_key(run_id, "curation:promoted")
            if replay:
                return replay.payload.memory_ids
            emit(
                uow,
                run,
                EventType.MEMORY_PROMOTED,
                "curation:promoted",
                utc_now(),
                EventPayload(
                    memory_ids=(receipt,),
                    summary=(
                        f"Approved curated memory {proposal.record.id}"
                        if proposal.status == "APPROVED"
                        else f"Staged curated memory {proposal.record.id} for review"
                    ),
                ),
                actor_id,
            )
            uow.commit()
            return (receipt,)

    def _stage_outcome(
        self,
        root: Path,
        run_id: UUID,
        commit: str,
        content: str,
        validation_id: str,
    ) -> MemoryProposal:
        store = CuratedMemoryStore(ProjectLayout(root))
        task_id = TaskCapsuleStore.from_root(root).capsule_id(run_id)
        if task_id is None:
            raise PolicyDeniedError("Memory promotion requires a persisted Task Capsule")
        title = f"Accepted task {task_id}"
        return store.propose_task_outcome(
            task_id,
            title,
            content,
            commit,
            evidence=(f"commit:{commit}", f"final-validation:{validation_id}"),
        )
