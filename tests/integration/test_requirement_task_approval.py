import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import Engine

from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.approval import (
    ApprovalDecisionKind,
    ApprovalStage,
    ApprovalStatus,
    ControlMode,
)
from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.provider import ProviderExecutionResult
from orqalis.persistence.database import session_factory
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis

pytestmark = pytest.mark.postgres


def test_opt_in_task_gate_holds_provider_requirements_work_at_plan_zero(
    database: Engine, git_repo: Path
) -> None:
    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    sdk = Orqalis(unit_of_work=factory)
    project = sdk.initialize(git_repo)
    run = sdk.prepare_run(
        project.id,
        "Check fixture",
        f"feature/requirements-gate-{uuid4().hex[:8]}",
        mode=ControlMode.SUPERVISED,
        gates=frozenset({ApprovalStage.TASK}),
    ).run
    draft = GoalDraft(
        goal="Check fixture",
        scope=("main.py",),
        definition_of_done=("File exists",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="File exists",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    )
    provider = FakeProvider(lambda _: ProviderExecutionResult(output=draft.model_dump(mode="json")))
    with pytest.raises(PolicyDeniedError, match="TASK approval required"):
        asyncio.run(sdk.requirements((provider,)).define(run.id, "fixture"))
    assert provider.calls == 0
    request = sdk.approvals.list(run.id)[-1]
    assert request.stage == ApprovalStage.TASK
    assert request.subject_version == 0
    assert request.status == ApprovalStatus.PENDING
    sdk.approvals.decide(
        run.id,
        request.id,
        ApprovalDecisionKind.APPROVE,
        "test-operator",
        request.subject_digest,
    )
    defined = asyncio.run(sdk.requirements((provider,)).define(run.id, "fixture"))
    assert defined.goal.version == 1
    assert provider.calls == 1
