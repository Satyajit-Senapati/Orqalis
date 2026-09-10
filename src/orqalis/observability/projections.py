from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from uuid import UUID

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import locked_run
from orqalis.core.scheduler import plan_completion
from orqalis.domain.base import utc_now
from orqalis.domain.projections import ActorProjection, PhaseProjection, RunSnapshot
from orqalis.domain.task import TaskStatus
from orqalis.domain.telemetry import ProviderCallProjection
from orqalis.domain.timing import TimingBreakdown
from orqalis.observability.analytics import statistics, timeline
from orqalis.observability.timing import EventTimingProjection


class ProjectionRepository(Protocol):
    def get_snapshot(self, run_id: UUID) -> RunSnapshot: ...


class SnapshotProjectionService:
    def __init__(
        self, unit_of_work: Callable[[], ProjectUnitOfWork], clock: Callable[[], datetime] = utc_now
    ) -> None:
        self.unit_of_work, self.clock = unit_of_work, clock

    def get_snapshot(self, run_id: UUID) -> RunSnapshot:
        # All run writers take this same lock, so rows and event cursor form one snapshot.
        with self.unit_of_work() as uow:
            run = locked_run(uow, run_id)
            now = self.clock()
            events = uow.events.list(run_id)
            if events:
                now = max(now, events[-1].occurred_at)
            timer = EventTimingProjection()
            goal = (
                uow.runs.get_goal(run.current_goal_version_id)
                if run.current_goal_version_id
                else None
            )
            plan = uow.runtime.get_plan(run_id, run.plan_version) if run.plan_version else None
            attempts = uow.runtime.executions(run_id)
            task_timing: dict[UUID, TimingBreakdown] = {}
            counts = {status: 0 for status in TaskStatus}
            all_tasks = uow.runtime.tasks(run_id)
            preparation = tuple(t for t in all_tasks if t.plan_version == 0)
            visible_tasks = plan.tasks if plan else preparation
            if visible_tasks:
                for task in visible_tasks:
                    counts[task.status] += 1
                    history = [attempt for attempt in attempts if attempt.task_id == task.id]
                    if history:
                        timings = [
                            timer.task(events, a.id, now).model_copy(
                                update={"queue_ms": a.queue_ms}
                            )
                            for a in history
                        ]
                        task_timing[task.id] = TimingBreakdown(
                            **{
                                field: sum(getattr(t, field) for t in timings)
                                for field in TimingBreakdown.model_fields
                            }
                        )
                    else:
                        queue = (
                            max(0, int((now - task.ready_at).total_seconds() * 1000))
                            if task.ready_at
                            else 0
                        )
                        task_timing[task.id] = TimingBreakdown(queue_ms=queue)
            evidence = []
            if goal:
                for criterion in goal.criteria:
                    for ref in criterion.evidence_refs:
                        item = uow.runs.get_evidence(ref)
                        if item:
                            evidence.append(item)
            run_timing = timer.run(events, now)
            segments = timeline(events, now)
            providers = uow.providers.list(run_id)
            tools = uow.execution.tools(run_id)
            reviews = uow.execution.reviews(run_id)
            guardians = uow.delivery.guardians(run_id)
            findings = uow.delivery.findings(run_id)
            blockers: list[str] = []
            if goal:
                blockers.extend(
                    f"{c.key}: {c.description}" for c in goal.criteria if c.status == "FAIL"
                )
            if reviews and reviews[-1].result.overall == "FAIL":
                blockers.extend(reviews[-1].result.blocking_findings)
                blockers.extend(c.reason for c in reviews[-1].result.criteria if c.status == "FAIL")
            if guardians and not guardians[-1].passed:
                blockers.extend(f.summary for f in guardians[-1].findings)
            if plan:
                blockers.extend(
                    f"Blocked task: {t.description}" for t in plan.tasks if t.status == "BLOCKED"
                )
            return RunSnapshot(
                run=run,
                goal=goal,
                plan=plan,
                actors=tuple(
                    ActorProjection(session=actor, timing=timer.actor(events, actor.id, now))
                    for actor in uow.runtime.actors(run_id)
                ),
                phases=tuple(
                    PhaseProjection(execution=phase, timing=timer.phase(events, phase.id, now))
                    for phase in uow.runtime.phases(run_id)
                ),
                attempts=attempts,
                task_timing=task_timing,
                evidence=tuple(evidence),
                timing=run_timing,
                tasks=all_tasks,
                preparation_tasks=preparation,
                timeline=segments,
                statistics=statistics(
                    segments, plan, task_timing, run_timing, providers, len(tools), reviews
                ),
                providers=tuple(
                    ProviderCallProjection(
                        id=p.id,
                        actor_session_id=p.actor_session_id,
                        task_execution_id=p.task_execution_id,
                        provider=p.provider,
                        model=p.model,
                        status=p.status,
                        started_at=p.started_at,
                        completed_at=p.completed_at,
                        error_code=p.error_code,
                        usage=p.result.usage if p.result else None,
                    )
                    for p in providers
                ),
                tools=tools,
                reviews=reviews,
                guardians=guardians,
                final_validations=uow.delivery.validations(run_id),
                delivery=uow.delivery.get(run_id),
                artifacts=uow.delivery.artifacts(run_id),
                findings=findings,
                blockers=tuple(dict.fromkeys(blockers)),
                task_counts=counts,
                plan_completion=plan_completion(plan) if plan else 0,
                server_time=now,
                last_event_sequence=run.last_event_sequence,
            )
