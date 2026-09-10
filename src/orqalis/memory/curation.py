import hashlib
from collections.abc import Callable
from uuid import UUID, uuid5

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit, locked_run
from orqalis.delivery.gates import guard_delivery
from orqalis.domain.agent import ActorStatus, AgentRole
from orqalis.domain.base import utc_now
from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.memory import MemoryItem, MemorySource, MemoryType
from orqalis.domain.run import RunState
from orqalis.git.service import LocalGitService
from orqalis.memory.service import MemoryService
from orqalis.security.redaction import safe_diagnostic


class MemoryCurator:
    """Promotes committed source summaries and verified run outcomes, never agent chatter."""

    def __init__(
        self, factory: Callable[[], ProjectUnitOfWork], memory: MemoryService, git: LocalGitService
    ) -> None:
        self.factory, self.memory, self.git = factory, memory, git

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
            if replay:
                return replay.payload.memory_ids
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
        # Index the exact accepted branch. Subsequent retrieval revalidates its own HEAD;
        # no checkout, merge or source-branch mutation is performed.
        self.memory.refresh(
            project.model_copy(update={"repo_root": workspace.path}), origin_run=run_id
        )
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            if run.state != RunState.MEMORY_FINALIZATION:
                raise PolicyDeniedError("Run left its memory curation checkpoint")
            guard_delivery(uow, run, RunState.MEMORY_FINALIZATION)
            uow.memory.lock_project(project.id)
            replay = uow.events.by_key(run_id, "curation:promoted")
            if replay:
                return replay.payload.memory_ids
            uow.memory.attribute_commit(project.id, delivery.commit_sha, run_id)
            summary = MemoryItem(
                id=uuid5(run_id, "curated-outcome"),
                project_id=project.id,
                type=MemoryType.PREVIOUS_RUN,
                title=f"Accepted run {run_id}",
                content=content,
                source_commit=delivery.commit_sha,
                introduced_by_run=run_id,
            )
            uow.memory.add_item(
                summary,
                MemorySource(
                    memory_item_id=summary.id,
                    source_type="git_commit",
                    source_ref=delivery.commit_sha,
                    content_hash=hashlib.sha256(delivery.commit_sha.encode()).hexdigest(),
                    commit_sha=delivery.commit_sha,
                ),
                None,
                None,
            )
            promoted = tuple(item.id for item in uow.memory.items_for_run(run_id))
            emit(
                uow,
                run,
                EventType.MEMORY_PROMOTED,
                "curation:promoted",
                utc_now(),
                EventPayload(
                    memory_ids=promoted,
                    summary=f"Promoted {len(promoted)} committed source/outcome facts",
                ),
                actor_id,
            )
            uow.commit()
            return promoted
