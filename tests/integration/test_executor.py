import asyncio
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import JsonValue

from orqalis.domain.acceptance import (
    CommandValidation,
    CriterionDefinition,
    GoalDraft,
    ReviewValidation,
)
from orqalis.domain.agent import ActorType, AgentRole
from orqalis.domain.capabilities import ToolName
from orqalis.domain.delivery import DeliveryPolicy
from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.events import EventType
from orqalis.domain.execution import (
    ApprovedCommand,
    CriterionReview,
    ExecutionPolicy,
    ReviewResult,
    SourceCheck,
    WorkerResult,
)
from orqalis.domain.memory import ContextPack
from orqalis.domain.project import ProjectSettings
from orqalis.domain.provider import (
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderToolCall,
)
from orqalis.domain.run import RunState
from orqalis.memory.curated import CuratedMemoryStore
from orqalis.persistence.filesystem import ProjectLayout, TaskCapsuleStore
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis
from tests.conftest import fixture_git
from tests.support.filesystem import filesystem_uow_factory


@pytest.mark.parametrize("forged_review,push", [(False, False), (False, True), (True, False)])
def test_isolated_developer_test_review_vertical_slice_and_resume(
    git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    forged_review: bool,
    push: bool,
) -> None:
    factory = filesystem_uow_factory(git_repo)

    sdk = Orqalis(unit_of_work=factory)
    project = sdk.initialize(git_repo, ProjectSettings(allow_push=push))
    command = ApprovedCommand(
        id="assert-answer",
        argv=(
            sys.executable,
            "-c",
            "from main import answer; assert answer == 43; print('assertion passed')",
        ),
    )
    goal = GoalDraft(
        goal="Change the answer to 43",
        scope=("main.py", "README.md"),
        definition_of_done=("Assertion and independent source review pass",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="Answer equals 43",
                validation_spec=CommandValidation(argv=command.argv),
            ),
            CriterionDefinition(
                key="AC-2",
                description="Implementation remains scoped",
                validation_spec=ReviewValidation(instructions="Check source"),
            ),
        ),
    )
    state = sdk.prepare_run(
        project.id, "Change the answer to 43", f"feature/slice-{uuid4().hex[:8]}", goal
    )

    def respond(request: ProviderExecutionRequest) -> ProviderExecutionResult:
        assert request.acceptance is not None
        if request.role == AgentRole.DEVELOPER:
            if not request.observations:
                return ProviderExecutionResult(
                    tool_calls=(
                        ProviderToolCall(
                            id="write-main",
                            name=ToolName.FILE_WRITE,
                            arguments={"path": "main.py", "content": "answer = 43\n"},
                        ),
                    )
                )
            return ProviderExecutionResult(
                output=WorkerResult(
                    summary="Updated the answer",
                    completed=True,
                    artifact_paths=("main.py",),
                ).model_dump(mode="json")
            )
        assert request.role == AgentRole.REVIEWER
        assert ToolName.FILE_WRITE not in {tool.name for tool in request.allowed_tools}
        assert request.selected_skills[0].metadata.id == "evidence-review"
        return ProviderExecutionResult(
            output=ReviewResult(
                overall="PASS",
                criteria=tuple(
                    CriterionReview(
                        criterion_id=item.id,
                        status="PASS",
                        reason="Verified actual evidence/source",
                        evidence_refs=() if forged_review else item.evidence_refs,
                        source_checks=(SourceCheck(path="main.py", contains="answer = 43"),)
                        if item.validation_spec.kind == "review"
                        else (),
                    )
                    for item in request.acceptance.criteria
                ),
                blocking_findings=(),
                non_blocking_findings=(),
            ).model_dump(mode="json")
        )

    provider = FakeProvider(respond)
    policy = ExecutionPolicy(
        write_paths=("main.py", "README.md"), commands=(command,), command_mode="trusted_local"
    )
    executor = sdk.executor(tmp_path / "worktrees", (provider,))
    execute_worker = executor.worker.execute

    async def finish_then_crash(
        run_id: UUID,
        attempt_id: UUID,
        provider_id: str,
        context: ContextPack,
        schema: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        await execute_worker(run_id, attempt_id, provider_id, context, schema)
        raise RuntimeError("simulated crash after worker result")

    with monkeypatch.context() as patch:
        patch.setattr(executor.worker, "execute", finish_then_crash)
        with pytest.raises(RuntimeError):
            asyncio.run(executor.execute(state.run.id, "fixture", policy))
    assert provider.calls == 2
    if forged_review:
        with pytest.raises(PolicyDeniedError):
            asyncio.run(executor.execute(state.run.id, "fixture", policy))
        assert sdk.snapshot(state.run.id).run.state == RunState.BLOCKED
        with factory() as uow:
            assert not uow.execution.reviews(state.run.id)
        return
    with factory() as lease:
        assert lease.execution.try_run_lock(state.run.id)
        with factory() as competitor:
            assert not competitor.execution.try_run_lock(state.run.id)
    summary = asyncio.run(executor.execute(state.run.id, "fixture", policy))
    assert summary.state == RunState.REVIEWING
    assert summary.review and summary.review.result.overall == "PASS"
    assert summary.completed_tasks == 3
    assert (summary.workspace / "main.py").read_text() == "answer = 43\n"
    assert (git_repo / "main.py").read_text() == "answer = 42\n"
    assert sdk.git.status(git_repo).branch == "main"
    assert all(path.startswith(".orqalis/") for path in sdk.git.status(git_repo).changed_paths)
    calls = provider.calls
    restarted = Orqalis(unit_of_work=factory).executor(tmp_path / "worktrees", (provider,))
    resumed = asyncio.run(restarted.execute(state.run.id, "fixture", policy))
    assert resumed.review == summary.review and provider.calls == calls
    snapshot = sdk.snapshot(state.run.id)
    assert {
        actor.session.role
        for actor in snapshot.actors
        if actor.session.actor_type == ActorType.AGENT
    } == {
        AgentRole.DEVELOPER,
        AgentRole.TESTER,
        AgentRole.REVIEWER,
    }
    assert all(criterion.status == "PASS" for criterion in sdk.goals.get(state.run.id).criteria)
    with factory() as uow:
        tools = uow.execution.tools(state.run.id)
        assert len(tools) == 1 and tools[0].status == "SUCCEEDED"
        events = uow.events.list(state.run.id)
        assert any(event.event_type == EventType.TEST_COMPLETED for event in events)
        assert any(event.event_type == EventType.REVIEW_COMPLETED for event in events)

    delivery_policy = DeliveryPolicy(
        documentation_path="README.md",
        push=push,
        allow_local_remote=push,
        author_name="Orqalis Test" if push else None,
        author_email="test@orqalis.invalid" if push else None,
    )
    remote = tmp_path / "remote.git"
    if push:
        fixture_git(tmp_path, "init", "--bare", str(remote))
        fixture_git(git_repo, "remote", "add", "origin", str(remote))
    fixture_git(summary.workspace, "config", "user.name", "Orqalis Test")
    fixture_git(summary.workspace, "config", "user.email", "test@orqalis.invalid")
    create_commit = sdk.delivery.commits.operations.create_commit
    created: list[str] = []

    def create_then_crash(*args: object, **kwargs: object) -> str:
        created.append(create_commit(*args, **kwargs))  # type: ignore[arg-type]
        raise RuntimeError("simulated crash after commit object creation")

    with monkeypatch.context() as patch:
        patch.setattr(sdk.delivery.commits.operations, "create_commit", create_then_crash)
        with pytest.raises(RuntimeError, match="commit object"):
            asyncio.run(sdk.delivery.finalize(state.run.id, delivery_policy))
    fixture_git(summary.workspace, "config", "user.name", "Changed after interruption")
    fixture_git(summary.workspace, "config", "user.email", "changed@orqalis.invalid")
    attach = sdk.delivery.commits.operations.attach

    def attach_then_crash(*args: object, **kwargs: object) -> None:
        attach(*args, **kwargs)  # type: ignore[arg-type]
        raise RuntimeError("simulated crash after branch attachment")

    with monkeypatch.context() as patch:
        patch.setattr(sdk.delivery.commits.operations, "attach", attach_then_crash)
        with pytest.raises(RuntimeError, match="branch attachment"):
            asyncio.run(sdk.delivery.finalize(state.run.id, delivery_policy))
    recovered = Orqalis(unit_of_work=factory)
    if push:
        original_push = recovered.delivery.commits.push

        def checked_push(run_id: UUID, actor_id: UUID) -> object:
            with pytest.raises(PolicyDeniedError, match="GitOps"):
                original_push(run_id, uuid4())
            fixture_git(git_repo, "config", "--add", "remote.origin.pushurl", str(remote))
            fixture_git(
                git_repo, "config", "--add", "remote.origin.pushurl", str(tmp_path / "second.git")
            )
            try:
                with pytest.raises(PolicyDeniedError, match="one push destination"):
                    original_push(run_id, actor_id)
            finally:
                fixture_git(git_repo, "config", "--unset-all", "remote.origin.pushurl")
            return original_push(run_id, actor_id)

        monkeypatch.setattr(recovered.delivery.commits, "push", checked_push)
    stage_outcome = recovered.delivery.curator._stage_outcome

    def stage_then_crash(
        root: Path,
        run_id: UUID,
        commit: str,
        content: str,
        validation_id: str,
    ) -> object:
        stage_outcome(root, run_id, commit, content, validation_id)
        raise RuntimeError("simulated crash after memory staging")

    with monkeypatch.context() as patch:
        patch.setattr(recovered.delivery.curator, "_stage_outcome", stage_then_crash)
        with pytest.raises(RuntimeError, match="memory staging"):
            asyncio.run(recovered.delivery.finalize(state.run.id, delivery_policy))
    delivered = asyncio.run(recovered.delivery.finalize(state.run.id, delivery_policy))
    assert delivered.state == RunState.COMPLETED
    assert delivered.commit_sha == created[0]
    assert delivered.pushed == push
    assert set(delivered.changed_paths) == {"main.py", "README.md"}
    assert sdk.git.status(summary.workspace).head == delivered.commit_sha
    assert not sdk.git.status(summary.workspace).changed_paths
    assert sdk.git.status(git_repo).branch == "main"
    assert (git_repo / "main.py").read_text() == "answer = 42\n"
    message = fixture_git(summary.workspace, "log", "-1", "--format=%B")
    assert str(state.run.id) in message and "Validation:" in message
    assert (summary.workspace / "README.md").read_text().count("<!-- orqalis:") == 2
    assert asyncio.run(recovered.delivery.finalize(state.run.id, delivery_policy)) == delivered
    if push:
        assert (
            fixture_git(remote, "rev-parse", f"refs/heads/{state.run.target_branch}")
            == delivered.commit_sha
        )
    with factory() as uow:
        identity = uow.events.by_key(state.run.id, "git:identity")
        assert identity and identity.payload.git_author_name == "Orqalis Test"
        assert len(uow.delivery.guardians(state.run.id)) == 2
        assert uow.delivery.validations(state.run.id)[-1].passed
        assert len(uow.delivery.artifacts(state.run.id)) == 2
        assert (
            sum(e.event_type == EventType.COMMIT_CREATED for e in uow.events.list(state.run.id))
            == 1
        )
    completed_snapshot = sdk.snapshot(state.run.id)
    assert completed_snapshot.run.repair_iteration == 0
    assert completed_snapshot.statistics.provider_calls == calls
    assert completed_snapshot.statistics.tool_calls == 1
    assert completed_snapshot.statistics.reported_input_tokens is None
    assert completed_snapshot.statistics.max_parallel_tasks == 1
    assert completed_snapshot.timeline and all(s.ended_at for s in completed_snapshot.timeline)
    assert completed_snapshot.artifacts and completed_snapshot.delivery
    assert completed_snapshot.statistics.critical_path_task_ids
    assert not completed_snapshot.blockers
    inspected = sdk.changes.diff(state.run.id, "main.py")
    assert "+answer = 43" in inspected.diff
    project_brain = sdk.brain.get(project.id, "architecture", state.run.id)
    assert project_brain.freshness.indexed_commit == delivered.commit_sha

    worktree_project = project.model_copy(update={"repo_root": summary.workspace})
    brain = recovered.memory.context(
        worktree_project, "architecture accepted run README", max_chars=50000
    )
    assert brain.freshness.fresh
    assert not (summary.workspace / ".orqalis").exists()
    capsule_id = TaskCapsuleStore.from_root(git_repo).capsule_id(state.run.id)
    assert capsule_id is not None
    curated = CuratedMemoryStore(ProjectLayout(git_repo))
    proposals = curated.proposals(capsule_id)
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.status == "PENDING"
    assert proposal.policy == "review"
    assert proposal.record.introduced_by_task == capsule_id
    assert proposal.record.verified_commit == delivered.commit_sha
    assert proposal.record.id not in {record.id for record in curated.list()}
    assert all(match.item.title != proposal.record.title for match in brain.items)
    with factory() as uow:
        promoted_events = [
            event
            for event in uow.events.list(state.run.id)
            if event.event_type == EventType.MEMORY_PROMOTED
        ]
        assert len(promoted_events) == 1
        assert promoted_events[0].payload.summary == (
            f"Staged curated memory {proposal.record.id} for review"
        )
    old_branch = recovered.memory.context(project, "README")
    assert all(m.item.title != "README.md" for m in old_branch.items)
    assert old_branch.freshness.current_commit == state.run.base_commit
