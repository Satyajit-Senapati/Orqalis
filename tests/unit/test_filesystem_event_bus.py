import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from orqalis.domain.events import EventDraft, EventType
from orqalis.domain.project import Project
from orqalis.domain.run import Run
from orqalis.observability.event_bus import ProjectEventBus
from orqalis.persistence.filesystem.task_store import TaskCapsuleStore
from orqalis.persistence.filesystem.unit_of_work import FilesystemProjectUnitOfWork


def project_run(root: Path) -> tuple[TaskCapsuleStore, Run]:
    root.mkdir()
    store = TaskCapsuleStore.from_root(root)
    project = Project(name="fixture", repo_root=root, default_branch="main")
    with FilesystemProjectUnitOfWork(store) as uow:
        uow.projects.add(project)
        uow.commit()
    run = Run(
        project_id=project.id,
        request="Prove committed notifications",
        target_branch="feature/events",
        base_commit="a" * 40,
    )
    with FilesystemProjectUnitOfWork(store) as uow:
        uow.runs.add(run)
        uow.commit()
    return store, run


def test_uow_publishes_only_after_event_commit(tmp_path: Path) -> None:
    async def exercise() -> None:
        store, run = project_run(tmp_path / "repo")
        bus = ProjectEventBus()
        async with bus.subscribe(run.id) as subscription:
            with FilesystemProjectUnitOfWork(store, bus) as uow:
                uow.events.append(
                    run.id,
                    EventDraft(
                        event_type=EventType.RUN_STARTED,
                        occurred_at=datetime.now(UTC),
                        idempotency_key="start",
                    ),
                )
                with pytest.raises(asyncio.TimeoutError):
                    await subscription.receive(timeout=0.01)
                uow.commit()
            assert (await subscription.receive(timeout=1)).sequence == 1

    asyncio.run(exercise())


def test_uow_does_not_publish_rolled_back_event(tmp_path: Path) -> None:
    async def exercise() -> None:
        store, run = project_run(tmp_path / "repo")
        bus = ProjectEventBus()
        async with bus.subscribe(run.id) as subscription:
            with FilesystemProjectUnitOfWork(store, bus) as uow:
                uow.events.append(
                    run.id,
                    EventDraft(
                        event_type=EventType.RUN_STARTED,
                        occurred_at=datetime.now(UTC),
                        idempotency_key="rolled-back",
                    ),
                )
                uow.rollback()
            with pytest.raises(asyncio.TimeoutError):
                await subscription.receive(timeout=0.01)

    asyncio.run(exercise())
