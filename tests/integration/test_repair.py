import asyncio
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import Engine

from orqalis.domain.acceptance import (
    CommandValidation,
    CriterionDefinition,
    FileValidation,
    GoalDraft,
)
from orqalis.domain.agent import AgentRole
from orqalis.domain.capabilities import ToolName
from orqalis.domain.execution import (
    ApprovedCommand,
    CriterionReview,
    ExecutionPolicy,
    ReviewResult,
    WorkerResult,
)
from orqalis.domain.project import ProjectSettings
from orqalis.domain.provider import (
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderToolCall,
)
from orqalis.domain.run import RunState
from orqalis.persistence.database import session_factory
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize(("converges", "limit"), [(True, 1), (False, 1), (False, 0)])
def test_targeted_repair_preserves_history_and_stops_at_limit(
    database: Engine,
    git_repo: Path,
    tmp_path: Path,
    converges: bool,
    limit: int,
) -> None:
    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    sdk = Orqalis(unit_of_work=factory)
    project = sdk.initialize(git_repo, ProjectSettings(max_repair_iterations=limit))
    command = ApprovedCommand(
        id="check",
        argv=(
            sys.executable,
            "-c",
            "from main import answer; assert answer == 43",
        ),
    )
    goal = GoalDraft(
        goal="Set answer to 43",
        scope=("main.py",),
        definition_of_done=("Behavior assertion passes",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="answer is 43",
                validation_spec=CommandValidation(argv=command.argv),
            ),
            CriterionDefinition(
                key="AC-2",
                description="Repository instructions remain",
                validation_spec=FileValidation(path="AGENTS.md"),
            ),
        ),
    )
    state = sdk.prepare_run(
        project.id, "Set answer to 43", f"feature/repair-{uuid4().hex[:8]}", goal
    )
    assert state.goal
    initial_goal_id = state.goal.goal.id

    def respond(request: ProviderExecutionRequest) -> ProviderExecutionResult:
        assert request.acceptance
        if request.role == AgentRole.DEVELOPER:
            if not request.observations:
                value = 43 if converges and request.task.plan_version > 1 else 44
                return ProviderExecutionResult(
                    tool_calls=(
                        ProviderToolCall(
                            id="write",
                            name=ToolName.FILE_WRITE,
                            arguments={"path": "main.py", "content": f"answer = {value}\n"},
                        ),
                    )
                )
            return ProviderExecutionResult(
                output=WorkerResult(
                    summary="Implemented candidate",
                    completed=True,
                    artifact_paths=("main.py",),
                ).model_dump(mode="json")
            )
        if request.role == AgentRole.REPAIR:
            assert request.evidence and any(
                not item.structured_data.passed for item in request.evidence
            )
            return ProviderExecutionResult(
                output=WorkerResult(
                    summary="main.py sets 44; the contract requires 43",
                    completed=True,
                    artifact_paths=(),
                ).model_dump(mode="json")
            )
        assert request.role == AgentRole.REVIEWER
        criteria = tuple(
            CriterionReview(
                criterion_id=item.id,
                status="PASS" if item.status == "PASS" else "FAIL",
                reason="Observed validator result",
                evidence_refs=item.evidence_refs[-1:],
                source_checks=(),
            )
            for item in request.acceptance.criteria
        )
        return ProviderExecutionResult(
            output=ReviewResult(
                overall="PASS" if all(item.status == "PASS" for item in criteria) else "FAIL",
                criteria=criteria,
                blocking_findings=(),
                non_blocking_findings=(),
            ).model_dump(mode="json")
        )

    provider = FakeProvider(respond)
    policy = ExecutionPolicy(
        write_paths=("main.py",), commands=(command,), command_mode="trusted_local"
    )
    summary = asyncio.run(
        sdk.executor(tmp_path / "worktrees", (provider,)).execute(state.run.id, "fixture", policy)
    )
    snapshot = sdk.snapshot(state.run.id)
    assert snapshot.run.repair_iteration == limit
    assert snapshot.run.plan_version == 1 + limit
    assert snapshot.run.current_goal_version_id == initial_goal_id
    assert snapshot.plan and len(snapshot.plan.tasks) == 3 + 4 * limit
    assert snapshot.run.state == (
        RunState.REVIEWING if converges else RunState.HUMAN_REVIEW_REQUIRED
    )
    assert summary.review and summary.review.result.overall == ("PASS" if converges else "FAIL")
    with factory() as uow:
        original = uow.runtime.get_plan(state.run.id, 1)
        assert original and len(original.tasks) == 3
        assert {task.id for task in original.tasks} <= {task.id for task in snapshot.plan.tasks}
        reviews = uow.execution.reviews(state.run.id)
        expected = ["FAIL", "PASS" if converges else "FAIL"] if limit else ["FAIL"]
        assert [review.result.overall for review in reviews] == expected
        assert len(uow.runtime.executions(state.run.id)) == 3 + 4 * limit
    assert (git_repo / "main.py").read_text() == "answer = 42\n"
    if limit:
        repair_tasks = [
            task
            for task in snapshot.plan.tasks
            if task.plan_version == 2
            and task.preferred_role
            in {
                AgentRole.DEVELOPER,
                AgentRole.REPAIR,
            }
        ]
        assert all(
            task.acceptance_criterion_ids == (state.goal.criteria[0].id,) for task in repair_tasks
        )
