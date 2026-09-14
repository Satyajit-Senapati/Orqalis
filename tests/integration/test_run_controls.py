"""Supervised approvals are durable and enforced by every execution interface."""

import asyncio
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine

from orqalis.api.app import create_app
from orqalis.config.settings import Settings
from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.approval import ApprovalDecisionKind, ApprovalStage, ApprovalStatus, ControlMode
from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.execution import ExecutionPolicy
from orqalis.domain.plan import TaskPlan
from orqalis.persistence.approvals import SQLApprovalRepository
from orqalis.persistence.database import session_factory
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis

pytestmark = pytest.mark.postgres


def fixture_goal() -> GoalDraft:
    return GoalDraft(
        goal="Inspect fixture",
        scope=("main.py",),
        definition_of_done=("file exists",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="Fixture exists",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    )


def test_executor_stops_before_workspace_at_goal_and_plan_gates(
    database: Engine, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def factory() -> SQLProjectUnitOfWork:
        return SQLProjectUnitOfWork(session_factory(database))

    sdk = Orqalis(unit_of_work=factory)
    project = sdk.initialize(git_repo)
    state = sdk.prepare_run(
        project.id,
        "Inspect fixture",
        f"feature/control-{uuid4().hex[:8]}",
        fixture_goal(),
        ControlMode.SUPERVISED,
    )
    workspaces = tmp_path / "worktrees"
    provider = FakeProvider(lambda _: pytest.fail("Provider ran before approval"))
    executor = sdk.executor(workspaces, (provider,))
    policy = ExecutionPolicy(write_paths=("main.py",))
    with pytest.raises(PolicyDeniedError, match="Goal approval required"):
        asyncio.run(executor.execute(state.run.id, "fixture", policy))
    assert not workspaces.exists()
    assert sdk.snapshot(state.run.id).run.state == "GOAL_DEFINED"
    goal_request = sdk.approvals.list(state.run.id)[-1]
    assert goal_request.stage == ApprovalStage.GOAL
    sdk.approvals.decide(
        state.run.id,
        goal_request.id,
        ApprovalDecisionKind.APPROVE,
        "test-operator",
        goal_request.subject_digest,
    )

    with pytest.raises(PolicyDeniedError, match="Plan approval required"):
        asyncio.run(executor.execute(state.run.id, "fixture", policy))
    assert not workspaces.exists()
    planned = sdk.snapshot(state.run.id)
    assert planned.run.state == "PLANNED"
    assert planned.plan is not None
    plan_request = sdk.approvals.list(state.run.id)[-1]
    assert plan_request.stage == ApprovalStage.PLAN
    sdk.approvals.decide(
        state.run.id,
        plan_request.id,
        ApprovalDecisionKind.APPROVE,
        "test-operator",
        plan_request.subject_digest,
    )
    assert sdk.approvals.get(state.run.id, plan_request.id).status == ApprovalStatus.APPROVED

    # The next invocation is allowed to allocate a workspace; provider work is
    # intentionally interrupted to avoid coupling this gate test to execution.
    def reached_workspace(*args: object) -> None:
        raise RuntimeError("workspace gate passed")

    with monkeypatch.context() as patch:
        patch.setattr(executor.workspaces, "ensure", reached_workspace)
        with pytest.raises(RuntimeError, match="workspace gate passed"):
            asyncio.run(executor.execute(state.run.id, "fixture", policy))


def test_local_api_requires_token_for_decisions_and_plan_edits(
    database: Engine, git_repo: Path
) -> None:
    sdk = Orqalis(
        settings=Settings(operator_token=SecretStr("test-operator-secret")),
        unit_of_work=lambda: SQLProjectUnitOfWork(session_factory(database)),
    )
    project = sdk.initialize(git_repo)
    state = sdk.prepare_run(
        project.id,
        "Inspect fixture",
        f"feature/api-control-{uuid4().hex[:8]}",
        fixture_goal(),
        ControlMode.SUPERVISED,
    )
    run_id = state.run.id
    with TestClient(
        create_app(sdk), base_url="http://localhost", client=("127.0.0.1", 50000)
    ) as client:
        preview = client.post(f"/api/runs/{run_id}/plan/preview", json={"idempotency_key": "first"})
        assert preview.status_code == 403
        preview = client.post(
            f"/api/runs/{run_id}/plan/preview",
            json={"idempotency_key": "first"},
            headers={"x-orqalis-operator-token": "test-operator-secret"},
        )
        assert preview.status_code == 403
        controls = client.get(f"/api/runs/{run_id}/controls").json()
        assert controls["policy"]["mode"] == "SUPERVISED"
        request = controls["approvals"][0]
        decision_url = f"/api/runs/{run_id}/approvals/{request['id']}/decision"
        command = {
            "decision": "APPROVE",
            "expected_subject_digest": request["subject_digest"],
            "reason": "Reviewed exact goal",
        }
        assert client.post(decision_url, json=command).status_code == 403
        assert (
            client.post(
                decision_url,
                json=command,
                headers={"x-orqalis-operator-token": "wrong"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                decision_url,
                json=command,
                headers={"x-orqalis-operator-token": "test-operator-secret"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/runs/{run_id}/plan/preview",
                json={"idempotency_key": "first"},
                headers={"x-orqalis-operator-token": "test-operator-secret"},
            ).status_code
            == 200
        )
        controls = client.get(f"/api/runs/{run_id}/controls").json()
        assert controls["approvals"][-1]["stage"] == "PLAN"
        assert controls["approvals"][-1]["subject_version"] == 1
        assert controls["approvals"][-1]["status"] == "PENDING"
        draft = client.get(f"/api/runs/{run_id}/plan/draft").json()
        assert draft["version"] == 2
        assert (
            client.post(
                f"/api/runs/{run_id}/plan/replace",
                json={"plan": draft, "expected_version": 1, "idempotency_key": "edit"},
            ).status_code
            == 403
        )
        replaced = client.post(
            f"/api/runs/{run_id}/plan/replace",
            json={"plan": draft, "expected_version": 1, "idempotency_key": "edit"},
            headers={"x-orqalis-operator-token": "test-operator-secret"},
        )
        assert replaced.status_code == 200, replaced.text
        assert TaskPlan.model_validate(replaced.json()).version == 2
        controls = client.get(f"/api/runs/{run_id}/controls").json()
        assert controls["approvals"][-1]["stage"] == "PLAN"
        assert controls["approvals"][-1]["subject_version"] == 2
        assert controls["approvals"][-1]["status"] == "PENDING"
        empty_token_sdk = Orqalis(
            settings=Settings(operator_token=SecretStr("")),
            unit_of_work=lambda: SQLProjectUnitOfWork(session_factory(database)),
        )
        with TestClient(
            create_app(empty_token_sdk),
            base_url="http://localhost",
            client=("127.0.0.1", 50001),
        ) as empty_token_client:
            assert empty_token_client.post(decision_url, json=command).status_code == 403


def test_supervised_policy_is_atomic_with_run_creation(
    database: Engine, git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sdk = Orqalis(unit_of_work=lambda: SQLProjectUnitOfWork(session_factory(database)))
    project = sdk.initialize(git_repo)

    def fail_policy_write(self: SQLApprovalRepository, policy: object) -> None:
        raise RuntimeError("simulated crash before commit")

    with monkeypatch.context() as patch:
        patch.setattr(SQLApprovalRepository, "save_policy", fail_policy_write)
        with pytest.raises(RuntimeError, match="simulated crash"):
            sdk.prepare_run(
                project.id,
                "Inspect fixture",
                f"feature/atomic-{uuid4().hex[:8]}",
                fixture_goal(),
                ControlMode.SUPERVISED,
            )
    assert sdk.list_runs(project.id) == ()

    def crash_after_creation(run_id: UUID) -> None:
        raise RuntimeError("crash after creation")

    with monkeypatch.context() as patch:
        patch.setattr(sdk, "continue_preparation", crash_after_creation)
        with pytest.raises(RuntimeError, match="crash after creation"):
            sdk.prepare_run(
                project.id,
                "Inspect fixture",
                f"feature/atomic-{uuid4().hex[:8]}",
                fixture_goal(),
                ControlMode.SUPERVISED,
            )
    persisted = sdk.list_runs(project.id)
    assert len(persisted) == 1
    assert sdk.approvals.policy(persisted[0].id).mode == ControlMode.SUPERVISED
