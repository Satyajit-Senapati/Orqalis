from collections.abc import Callable
from uuid import UUID, uuid5

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit, locked_run
from orqalis.delivery.gates import guard_delivery
from orqalis.domain.agent import ActorStatus, AgentRole
from orqalis.domain.base import utc_now
from orqalis.domain.delivery import DeliveryPolicy, GitDelivery
from orqalis.domain.errors import ConflictError, NotFoundError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.run import RunState
from orqalis.git.delivery import GitDeliveryService
from orqalis.git.service import LocalGitService


class CommitService:
    def __init__(self, factory: Callable[[], ProjectUnitOfWork], git: LocalGitService) -> None:
        self.factory, self.git = factory, git
        self.operations = GitDeliveryService(git)

    def commit(self, run_id: UUID, policy: DeliveryPolicy, actor_id: UUID) -> GitDelivery:
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            if run.state != RunState.COMMITTING:
                raise PolicyDeniedError("Commit requires the committing checkpoint")
            actor = next((a for a in uow.runtime.actors(run_id) if a.id == actor_id), None)
            if not actor or actor.role != AgentRole.GITOPS or actor.status != ActorStatus.WORKING:
                raise PolicyDeniedError("Commit requires an active GitOps actor")
            guard_delivery(uow, run, RunState.COMMITTING)
            workspace = uow.execution.workspace(run_id)
            project = uow.projects.get(run.project_id)
            if workspace is None or project is None:
                raise NotFoundError("Delivery workspace/project missing")
            if project is not None and policy.push and not project.settings.allow_push:
                raise PolicyDeniedError("Project policy forbids pushing")
            delivery = uow.delivery.get(run_id)
            if delivery and delivery.policy != policy:
                raise ConflictError("Delivery policy is immutable once delivery begins")
            identity = uow.events.by_key(run_id, "git:identity")
            if identity is None and (delivery is None or delivery.commit_sha is None):
                name = (
                    policy.author_name
                    or self.git._execute(workspace.path, ("config", "--get", "user.name"))
                    .decode()
                    .strip()
                )
                email = (
                    policy.author_email
                    or self.git._execute(workspace.path, ("config", "--get", "user.email"))
                    .decode()
                    .strip()
                )
                resolved = DeliveryPolicy.model_validate(
                    policy.model_dump() | {"author_name": name, "author_email": email}
                )
                identity = emit(
                    uow,
                    run,
                    EventType.APPROVAL_RECORDED,
                    "git:identity",
                    utc_now(),
                    EventPayload(
                        git_author_name=resolved.author_name,
                        git_author_email=resolved.author_email,
                        summary="Git author identity resolved",
                    ),
                    actor_id,
                )
            if delivery is None:
                report = [r for r in uow.delivery.guardians(run_id) if r.checkpoint == "final"][-1]
                tree = self.operations.stage(workspace, report, project.settings.protected_branches)
                goal = (
                    uow.runs.get_goal(run.current_goal_version_id)
                    if run.current_goal_version_id
                    else None
                )
                assert goal is not None
                message = (
                    f"feat: {goal.goal.goal.splitlines()[0][:100]}\n\n"
                    f"Orqalis-Run: {run_id}\nGoal-Version: {goal.goal.version}\n"
                    f"Base-Commit: {workspace.base_commit}\n\nChanges:\n"
                    + "\n".join(f"- {c.status}: {c.path}" for c in report.changes)
                    + "\n\nValidation: all required criteria passed; independent review, "
                    "Change Guardian, documentation and final validation passed.\n"
                )
                delivery = GitDelivery(
                    id=uuid5(run_id, "git-delivery"),
                    run_id=run_id,
                    branch=workspace.branch,
                    base_commit=workspace.base_commit,
                    tree_hash=report.tree_hash,
                    git_tree_sha=tree,
                    commit_message=message,
                    policy=policy,
                    remote=policy.remote if policy.push else None,
                    push_status="pending" if policy.push else "not_requested",
                )
                uow.delivery.save(delivery)
                uow.commit()
            elif identity:
                uow.commit()
        state = self.git.status(workspace.path)
        if state.head == workspace.base_commit:
            with self.factory() as uow:
                final = [r for r in uow.delivery.guardians(run_id) if r.checkpoint == "final"][-1]
            tree = self.operations.stage(workspace, final, project.settings.protected_branches)
            if tree != delivery.git_tree_sha:
                raise ConflictError("Staged tree no longer matches the commit intent")
        elif state.head != delivery.commit_sha or state.changed_paths:
            raise ConflictError("Workspace changed after commit intent")
        # Commit object creation is deterministic, including its persisted timestamp.
        if delivery.commit_sha is None:
            assert identity is not None
            resolved_policy = policy.model_copy(
                update={
                    "author_name": identity.payload.git_author_name,
                    "author_email": identity.payload.git_author_email,
                }
            )
            sha = self.operations.create_commit(
                workspace,
                delivery.git_tree_sha,
                delivery.commit_message,
                delivery.created_at,
                resolved_policy,
            )
            delivery = delivery.model_copy(update={"commit_sha": sha})
            with self.factory() as uow:
                locked_run(uow, run_id)
                uow.delivery.save(delivery)
                uow.commit()
        assert delivery.commit_sha is not None
        self.operations.attach(workspace, delivery.commit_sha, project.settings.protected_branches)
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            delivery = delivery.model_copy(update={"commit_attached": True})
            uow.delivery.save(delivery)
            emit(
                uow,
                run,
                EventType.COMMIT_CREATED,
                f"commit:{delivery.id}",
                utc_now(),
                EventPayload(summary=delivery.commit_sha),
                actor_id,
            )
            uow.commit()
        return delivery

    def push(self, run_id: UUID, actor_id: UUID) -> GitDelivery:
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            if run.state != RunState.PUSHING:
                raise PolicyDeniedError("Push requires the pushing checkpoint")
            actor = next((a for a in uow.runtime.actors(run_id) if a.id == actor_id), None)
            if not actor or actor.role != AgentRole.GITOPS or actor.status != ActorStatus.WORKING:
                raise PolicyDeniedError("Push requires an active GitOps actor")
            guard_delivery(uow, run, RunState.PUSHING)
            delivery = uow.delivery.get(run_id)
            workspace = uow.execution.workspace(run_id)
            project = uow.projects.get(run.project_id)
            assert delivery and delivery.commit_sha and workspace and project
            if not project.settings.allow_push:
                raise PolicyDeniedError("Project policy forbids pushing")
        if delivery.push_status == "pushed":
            return delivery
        self.operations.push(
            workspace, delivery.commit_sha, delivery.policy, project.settings.protected_branches
        )
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            delivery = delivery.model_copy(update={"push_status": "pushed"})
            uow.delivery.save(delivery)
            emit(
                uow,
                run,
                EventType.PUSH_COMPLETED,
                f"push:{delivery.id}",
                utc_now(),
                EventPayload(summary=delivery.commit_sha),
                actor_id,
            )
            uow.commit()
        return delivery
