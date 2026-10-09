from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest

from orqalis.domain.artifact import Artifact, Finding
from orqalis.domain.capabilities import ToolName
from orqalis.domain.delivery import ChangeReport, DeliveryPolicy, FinalValidation, GitDelivery
from orqalis.domain.errors import ConflictError
from orqalis.domain.execution import (
    ExecutionPolicy,
    ReviewRecord,
    ReviewResult,
    RunWorkspace,
    ToolInvocation,
)
from orqalis.domain.memory import ProjectSnapshot
from orqalis.domain.project import Project
from orqalis.domain.provider import InvocationStatus, ProviderExecution
from orqalis.domain.run import Run
from orqalis.persistence.filesystem.locking import FileLock, LockTimeoutError
from orqalis.persistence.filesystem.task_store import TaskCapsuleStore
from orqalis.persistence.filesystem.unit_of_work import FilesystemProjectUnitOfWork


def _initialized_store(root: Path) -> tuple[TaskCapsuleStore, Project, Run]:
    root.mkdir()
    store = TaskCapsuleStore.from_root(root)
    project = Project(name="fixture", repo_root=root, default_branch="main")
    run = Run(
        project_id=project.id,
        request="Persist auxiliary run state",
        target_branch="feature/filesystem-uow",
        base_commit="a" * 40,
    )
    with FilesystemProjectUnitOfWork(store) as uow:
        uow.projects.add(project)
        uow.runs.add(run)
        uow.commit()
    return store, project, run


def test_auxiliary_repositories_roundtrip_restart_and_preserve_semantics(
    tmp_path: Path,
) -> None:
    store, project, run = _initialized_store(tmp_path / "repo")
    workspace_path = store.root / "worktrees" / "task"
    workspace_path.mkdir(parents=True)
    workspace = RunWorkspace(
        run_id=run.id,
        path=workspace_path,
        base_commit=run.base_commit,
        branch=run.target_branch,
        policy=ExecutionPolicy(write_paths=("src/**",), command_mode="trusted_local"),
    )
    actor_id, task_execution_id = uuid4(), uuid4()
    early_provider = ProviderExecution(
        run_id=run.id,
        task_execution_id=task_execution_id,
        actor_session_id=actor_id,
        provider="fixture",
        model="model-a",
        request_hash="b" * 64,
        idempotency_key="provider-early",
        started_at=run.created_at,
        deadline_at=run.created_at + timedelta(minutes=1),
    )
    late_provider = ProviderExecution(
        run_id=run.id,
        task_execution_id=task_execution_id,
        actor_session_id=actor_id,
        provider="fixture",
        model="model-b",
        request_hash="c" * 64,
        idempotency_key="provider-late",
        started_at=run.created_at + timedelta(seconds=1),
        deadline_at=run.created_at + timedelta(minutes=1),
    )
    early_tool = ToolInvocation(
        run_id=run.id,
        task_execution_id=task_execution_id,
        actor_session_id=actor_id,
        provider_invocation_id=early_provider.id,
        call_id="call-early",
        tool=ToolName.FILE_READ,
        request_hash="d" * 64,
        started_at=run.created_at,
    )
    late_tool = ToolInvocation(
        run_id=run.id,
        task_execution_id=task_execution_id,
        actor_session_id=actor_id,
        provider_invocation_id=late_provider.id,
        call_id="call-late",
        tool=ToolName.TEST_RUN,
        request_hash="e" * 64,
        started_at=run.created_at + timedelta(seconds=1),
    )
    review = ReviewRecord(
        run_id=run.id,
        goal_version_id=uuid4(),
        plan_version=1,
        actor_session_id=actor_id,
        tree_hash="f" * 64,
        result=ReviewResult(
            overall="PASS",
            criteria=(),
            blocking_findings=(),
            non_blocking_findings=(),
        ),
    )
    finding = Finding(
        run_id=run.id,
        severity="warning",
        category="scope",
        summary="Inspect the generated file",
    )
    guardian = ChangeReport(
        run_id=run.id,
        actor_session_id=actor_id,
        checkpoint="final",
        base_commit=run.base_commit,
        tree_hash="1" * 64,
        passed=False,
        changes=(),
        findings=(finding,),
    )
    validation = FinalValidation(
        run_id=run.id,
        actor_session_id=actor_id,
        goal_version_id=review.goal_version_id,
        tree_hash=guardian.tree_hash,
        passed=True,
        evidence_ids=(),
    )
    delivery = GitDelivery(
        run_id=run.id,
        base_commit=run.base_commit,
        branch=run.target_branch,
        tree_hash=guardian.tree_hash,
        git_tree_sha="2" * 40,
        commit_message="Persist local state",
        policy=DeliveryPolicy(),
    )
    artifact = Artifact(
        run_id=run.id,
        type="report",
        path_or_uri="artifacts/report.json",
        content_hash="3" * 64,
    )
    snapshot = ProjectSnapshot(
        project_id=project.id,
        indexed_commit_sha=run.base_commit,
        repo_fingerprint="4" * 64,
        files_scanned=1,
    )

    with FilesystemProjectUnitOfWork(store) as uow:
        uow.execution.save_workspace(workspace)
        uow.execution.save_tool(late_tool)
        uow.execution.save_tool(early_tool)
        completed_tool = early_tool.model_copy(
            update={"status": "SUCCEEDED", "completed_at": run.created_at}
        )
        uow.execution.save_tool(completed_tool)
        uow.execution.save_review(review)
        with pytest.raises(ConflictError, match="Review identity"):
            uow.execution.save_review(review)

        uow.providers.save(late_provider)
        uow.providers.save(early_provider)
        completed_provider = early_provider.model_copy(
            update={"status": InvocationStatus.SUCCEEDED, "completed_at": run.created_at}
        )
        uow.providers.save(completed_provider)
        duplicate_key = late_provider.model_copy(
            update={"id": uuid4(), "idempotency_key": early_provider.idempotency_key}
        )
        with pytest.raises(ConflictError, match="idempotency"):
            uow.providers.save(duplicate_key)

        uow.delivery.save_guardian(guardian)
        with pytest.raises(ConflictError, match="Change report identity"):
            uow.delivery.save_guardian(guardian)
        uow.delivery.save_validation(validation)
        with pytest.raises(ConflictError, match="validation identity"):
            uow.delivery.save_validation(validation)
        uow.delivery.save(delivery)
        attached_delivery = delivery.model_copy(
            update={"commit_attached": True, "commit_sha": "5" * 40}
        )
        uow.delivery.save(attached_delivery)
        uow.delivery.save_artifact(artifact)
        updated_artifact = artifact.model_copy(update={"content_hash": "6" * 64})
        uow.delivery.save_artifact(updated_artifact)
        resolved_finding = finding.model_copy(update={"status": "resolved"})
        uow.delivery.save_finding(resolved_finding)
        uow.memory.save_snapshot(snapshot)
        uow.commit()

    capsule_id = store.capsule_id(run.id)
    assert capsule_id is not None
    state = (store.layout.task(capsule_id) / "execution" / "state.yaml").read_text()
    assert str(store.root.resolve()) not in state
    assert '"scope": "project"' in state
    assert '"value": "worktrees/task"' in state

    restarted = TaskCapsuleStore.from_root(store.root)
    with FilesystemProjectUnitOfWork(restarted) as uow:
        assert uow.execution.workspace(run.id) == workspace
        assert uow.execution.tools(run.id) == (completed_tool, late_tool)
        assert uow.execution.tool(early_tool.id) == completed_tool
        assert uow.execution.reviews(run.id) == (review,)
        assert uow.providers.list(run.id) == (completed_provider, late_provider)
        assert uow.providers.get(early_provider.id) == completed_provider
        assert uow.delivery.guardians(run.id) == (guardian,)
        assert uow.delivery.validations(run.id) == (validation,)
        assert uow.delivery.get(run.id) == attached_delivery
        assert uow.delivery.artifacts(run.id) == (updated_artifact,)
        assert uow.delivery.findings(run.id) == (resolved_finding,)
        assert uow.memory.latest_snapshot(project.id) == snapshot


def test_full_uow_rollback_discards_capsule_extensions_and_memory(tmp_path: Path) -> None:
    store, project, run = _initialized_store(tmp_path / "repo")
    workspace = RunWorkspace(
        run_id=run.id,
        path=store.root,
        base_commit=run.base_commit,
        branch=run.target_branch,
        policy=ExecutionPolicy(write_paths=("*",), command_mode="trusted_local"),
    )
    snapshot = ProjectSnapshot(
        project_id=project.id,
        indexed_commit_sha=run.base_commit,
        repo_fingerprint="7" * 64,
        files_scanned=0,
    )

    with FilesystemProjectUnitOfWork(store) as uow:
        uow.execution.save_workspace(workspace)
        uow.memory.save_snapshot(snapshot)
        uow.rollback()

    with FilesystemProjectUnitOfWork(TaskCapsuleStore.from_root(store.root)) as uow:
        assert uow.execution.workspace(run.id) is None
        assert uow.memory.latest_snapshot(project.id) is None


def test_controller_lease_is_held_until_full_uow_closes(tmp_path: Path) -> None:
    store, _, run = _initialized_store(tmp_path / "repo")
    owner = FilesystemProjectUnitOfWork(store)
    assert owner.execution.try_run_lock(run.id)

    def contend() -> bool:
        with FilesystemProjectUnitOfWork(TaskCapsuleStore.from_root(store.root)) as other:
            return other.execution.try_run_lock(run.id)

    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(contend).result(timeout=2) is False
    owner.close()

    with FilesystemProjectUnitOfWork(TaskCapsuleStore.from_root(store.root)) as successor:
        assert successor.execution.try_run_lock(run.id)


def test_task_only_uow_preserves_unrelated_corrupt_source_projection(tmp_path: Path) -> None:
    store, _, run = _initialized_store(tmp_path / "repo")
    projection = store.layout.cache / "graph" / "legacy-projection.json"
    projection.parent.mkdir(parents=True, exist_ok=True)
    corrupt = b'{"schema_version": 1, "entities": "invalid", "relations": []}\n'
    projection.write_bytes(corrupt)
    # Task state remains available independently of its rebuildable memory cache.
    with FilesystemProjectUnitOfWork(store) as uow:
        assert uow.runs.get(run.id, for_update=True) == run
        uow.commit()
    with FilesystemProjectUnitOfWork(store) as uow:
        assert uow.runs.get(run.id, for_update=True) == run
        uow.rollback()
    assert projection.read_bytes() == corrupt
    # Deferring construction must not bypass validation on actual memory access.
    with (
        FilesystemProjectUnitOfWork(store) as uow,
        pytest.raises(ConflictError, match="Compatibility graph is invalid"),
    ):
        uow.memory.graph(run.project_id)
    assert projection.read_bytes() == corrupt


def test_delayed_memory_access_observes_commit_and_releases_its_lock(tmp_path: Path) -> None:
    store, project, _ = _initialized_store(tmp_path / "repo")
    snapshot = ProjectSnapshot(
        project_id=project.id,
        indexed_commit_sha="b" * 40,
        repo_fingerprint="c" * 64,
        files_scanned=0,
    )
    with FilesystemProjectUnitOfWork(store) as reader:
        with FilesystemProjectUnitOfWork(store) as writer:
            writer.memory.save_snapshot(snapshot)
            writer.commit()
        assert reader.memory.latest_snapshot(project.id) == snapshot
        reader.memory.lock_project(project.id)
    # Exiting still releases the memory write lease before a fresh transaction.
    with FilesystemProjectUnitOfWork(store) as successor:
        successor.memory.lock_project(project.id)
        assert successor.memory.latest_snapshot(project.id) == snapshot
    with pytest.raises(RuntimeError, match="closed"):
        reader.memory.latest_snapshot(project.id)


@pytest.mark.parametrize("operation", ["read", "upsert"])
def test_parallel_provider_identity_checks_do_not_invert_run_locks(
    tmp_path: Path, operation: str
) -> None:
    store, _, first = _initialized_store(tmp_path / "repo")
    second = first.model_copy(update={"id": uuid4()})
    with FilesystemProjectUnitOfWork(store) as uow:
        uow.runs.add(second)
        uow.commit()
    invocations = [
        ProviderExecution(
            run_id=run.id,
            task_execution_id=uuid4(),
            actor_session_id=uuid4(),
            provider="fixture",
            model="fixture",
            request_hash="b" * 64,
            idempotency_key="provider",
            started_at=run.created_at,
            deadline_at=run.created_at + timedelta(minutes=1),
        )
        for run in (first, second)
    ]
    with FilesystemProjectUnitOfWork(store) as uow:
        for invocation in invocations:
            uow.providers.save(invocation)
        uow.commit()
    both_locked = Barrier(2)

    def check(invocation: ProviderExecution) -> None:
        with FilesystemProjectUnitOfWork(TaskCapsuleStore.from_root(store.root)) as uow:
            assert uow.runs.get(invocation.run_id, for_update=True) is not None
            both_locked.wait(timeout=15)
            if operation == "read":
                assert uow.providers.get(invocation.id) == invocation
            else:
                uow.providers.save(invocation)
                uow.commit()

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [pool.submit(check, invocation) for invocation in invocations]
        for result in pending:
            result.result(timeout=20)


def _provider_for(run: Run) -> ProviderExecution:
    return ProviderExecution(
        run_id=run.id,
        task_execution_id=uuid4(),
        actor_session_id=uuid4(),
        provider="fixture",
        model="fixture",
        request_hash="b" * 64,
        idempotency_key="provider",
        started_at=run.created_at,
        deadline_at=run.created_at + timedelta(minutes=1),
    )


def test_concurrent_cross_run_identity_claim_has_one_owner(tmp_path: Path) -> None:
    store, _, first = _initialized_store(tmp_path / "repo")
    second = first.model_copy(update={"id": uuid4()})
    with FilesystemProjectUnitOfWork(store) as uow:
        uow.runs.add(second)
        uow.commit()
    invocation = _provider_for(first)
    both_locked = Barrier(2)

    def claim(run: Run) -> str:
        with FilesystemProjectUnitOfWork(TaskCapsuleStore.from_root(store.root)) as uow:
            assert uow.runs.get(run.id, for_update=True) is not None
            both_locked.wait(timeout=15)
            try:
                uow.providers.save(invocation.model_copy(update={"run_id": run.id}))
            except ConflictError as exc:
                assert "belongs to another run" in str(exc)
                return "rejected"
            uow.commit()
            return "saved"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [pool.submit(claim, run) for run in (first, second)]
        assert sorted(result.result(timeout=20) for result in outcomes) == ["rejected", "saved"]
    with FilesystemProjectUnitOfWork(store) as uow:
        assert len(uow.providers.list(first.id)) + len(uow.providers.list(second.id)) == 1


def test_identity_handoff_rejects_stale_staged_run_and_releases_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, _, run = _initialized_store(tmp_path / "repo")
    native_acquire = FileLock.acquire
    changed = run.model_copy(update={"request": "Concurrent control update"})
    intercepted = False

    def change_during_handoff(lock: FileLock) -> None:
        nonlocal intercepted
        if lock.path.name == "auxiliary-identities.lock" and not intercepted:
            intercepted = True
            with FilesystemProjectUnitOfWork(store) as writer:
                writer.runs.save(changed)
                writer.commit()
        native_acquire(lock)

    with FilesystemProjectUnitOfWork(store) as uow:
        assert uow.runs.get(run.id, for_update=True) == run
        uow.runs.save(run.model_copy(update={"request": "Stale staged update"}))
        with monkeypatch.context() as patch:
            patch.setattr(FileLock, "acquire", change_during_handoff)
            with pytest.raises(ConflictError, match="changed during identity lock handoff"):
                uow.providers.save(_provider_for(run))
        assert intercepted
        with pytest.raises(ConflictError, match="requires rollback"):
            uow.commit()
        with pytest.raises(ConflictError, match="requires rollback"):
            uow.runs.get(run.id)
        with pytest.raises(ConflictError, match="requires rollback"):
            uow.providers.get(uuid4(), run_id=run.id)
        with pytest.raises(ConflictError, match="requires rollback"):
            uow.runs.add(run.model_copy(update={"id": uuid4()}))
        with pytest.raises(ConflictError, match="requires rollback"):
            tuple(uow.session.iter_capsules())
        uow.rollback()
        assert uow.runs.get(run.id) == changed
    with FilesystemProjectUnitOfWork(store) as successor:
        successor.providers.save(_provider_for(changed))
        successor.commit()


@pytest.mark.parametrize("failure", ["lease", "reacquire"])
def test_failed_identity_handoff_releases_all_owned_locks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    store, _, run = _initialized_store(tmp_path / "repo")
    native_acquire = FileLock.acquire

    def fail_acquire(lock: FileLock) -> None:
        target = "auxiliary-identities.lock" if failure == "lease" else ".state.lock"
        if lock.path.name.endswith(target):
            raise LockTimeoutError("Injected acquisition failure")
        native_acquire(lock)

    with FilesystemProjectUnitOfWork(store) as uow:
        assert uow.runs.get(run.id, for_update=True) == run
        with monkeypatch.context() as patch:
            patch.setattr(FileLock, "acquire", fail_acquire)
            with pytest.raises(LockTimeoutError, match="Injected"):
                uow.providers.save(_provider_for(run))
        with pytest.raises(ConflictError, match="requires rollback"):
            uow.commit()
        with pytest.raises(ConflictError, match="requires rollback"):
            uow.runs.get(run.id)
        with pytest.raises(ConflictError, match="requires rollback"):
            uow.providers.get(uuid4(), run_id=run.id)
        with pytest.raises(ConflictError, match="requires rollback"):
            uow.runs.add(run.model_copy(update={"id": uuid4()}))
        with pytest.raises(ConflictError, match="requires rollback"):
            tuple(uow.session.iter_capsules())
        # A different transaction can take both leases before the failed one exits.
        with FilesystemProjectUnitOfWork(store) as successor:
            assert successor.runs.get(run.id, for_update=True) == run
            successor.providers.save(_provider_for(run))
            successor.commit()
        uow.rollback()


def test_nested_identity_owner_and_memory_lock_order_fail_fast(tmp_path: Path) -> None:
    store, project, run = _initialized_store(tmp_path / "repo")
    invocation = _provider_for(run)
    with FilesystemProjectUnitOfWork(store) as owner:
        owner.providers.save(invocation)
        with FilesystemProjectUnitOfWork(store) as nested:
            with pytest.raises(ConflictError, match="Nested transactions"):
                nested.providers.get(invocation.id)
            assert nested.providers.get(invocation.id, run_id=uuid4()) is None
        owner.rollback()
    with FilesystemProjectUnitOfWork(store) as memory_first:
        memory_first.memory.lock_project(project.id)
        with pytest.raises(ConflictError, match="before the source-memory write lease"):
            memory_first.providers.save(invocation)
        memory_first.rollback()
    with FilesystemProjectUnitOfWork(store) as ordered:
        ordered.providers.save(invocation)
        ordered.memory.lock_project(project.id)
        ordered.commit()
    with FilesystemProjectUnitOfWork(store) as reader:
        assert reader.providers.get(invocation.id, run_id=run.id) == invocation
        assert reader.providers.get(invocation.id, run_id=uuid4()) is None
        assert reader.session._auxiliary_lock is None


def test_new_capsule_auxiliary_claim_keeps_reservation_and_rolls_back(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    store = TaskCapsuleStore.from_root(root)
    project = Project(name="fixture", repo_root=root, default_branch="main")
    run = Run(
        project_id=project.id,
        request="New capsule",
        target_branch="feature/new",
        base_commit="a" * 40,
    )
    invocation = _provider_for(run)
    with FilesystemProjectUnitOfWork(store) as uow:
        uow.projects.add(project)
        uow.runs.add(run)
        uow.providers.save(invocation)
        uow.commit()
    with FilesystemProjectUnitOfWork(store) as reader:
        assert reader.providers.get(invocation.id) == invocation
    abandoned = run.model_copy(update={"id": uuid4()})
    abandoned_invocation = _provider_for(abandoned)
    with FilesystemProjectUnitOfWork(store) as uow:
        uow.runs.add(abandoned)
        uow.providers.save(abandoned_invocation)
        uow.rollback()
    with FilesystemProjectUnitOfWork(store) as reader:
        assert reader.runs.get(abandoned.id) is None
        assert reader.providers.get(abandoned_invocation.id) is None


def test_identity_lease_refreshes_foreign_read_cache(tmp_path: Path) -> None:
    store, _, first = _initialized_store(tmp_path / "repo")
    second = first.model_copy(update={"id": uuid4()})
    with FilesystemProjectUnitOfWork(store) as uow:
        uow.runs.add(second)
        uow.commit()
    invocation = _provider_for(second)
    with FilesystemProjectUnitOfWork(store) as earlier:
        assert earlier.runs.get(first.id, for_update=True) == first
        assert earlier.runs.get(second.id) == second
        with FilesystemProjectUnitOfWork(store) as writer:
            writer.providers.save(invocation)
            writer.commit()
        with pytest.raises(ConflictError, match="belongs to another run"):
            earlier.providers.save(invocation.model_copy(update={"run_id": first.id}))
    with FilesystemProjectUnitOfWork(store) as reader:
        assert reader.providers.list(first.id) == ()
        assert reader.providers.list(second.id) == (invocation,)
