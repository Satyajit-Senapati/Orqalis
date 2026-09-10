from uuid import UUID

from pydantic import AwareDatetime, Field

from orqalis.domain.acceptance import GoalContract
from orqalis.domain.agent import ActorSession
from orqalis.domain.artifact import Artifact, Evidence, Finding
from orqalis.domain.base import Contract
from orqalis.domain.delivery import ChangeReport, FinalValidation, GitDelivery
from orqalis.domain.execution import ReviewRecord, ToolInvocation
from orqalis.domain.plan import TaskPlan
from orqalis.domain.run import Run
from orqalis.domain.task import Task, TaskExecution, TaskStatus
from orqalis.domain.telemetry import ProviderCallProjection, RuntimeStatistics, TimelineSegment
from orqalis.domain.timing import PhaseExecution, TimingBreakdown


class ActorProjection(Contract):
    session: ActorSession
    timing: TimingBreakdown


class PhaseProjection(Contract):
    execution: PhaseExecution
    timing: TimingBreakdown


class RunSnapshot(Contract):
    run: Run
    goal: GoalContract | None
    plan: TaskPlan | None
    actors: tuple[ActorProjection, ...]
    phases: tuple[PhaseProjection, ...]
    attempts: tuple[TaskExecution, ...]
    task_timing: dict[UUID, TimingBreakdown]
    evidence: tuple[Evidence, ...]
    timing: TimingBreakdown
    task_counts: dict[TaskStatus, int]
    plan_completion: float = Field(ge=0, le=100)
    server_time: AwareDatetime
    last_event_sequence: int

    tasks: tuple[Task, ...] = ()
    preparation_tasks: tuple[Task, ...] = ()
    timeline: tuple[TimelineSegment, ...] = ()
    statistics: RuntimeStatistics = Field(default_factory=RuntimeStatistics)
    providers: tuple[ProviderCallProjection, ...] = ()
    tools: tuple[ToolInvocation, ...] = ()
    reviews: tuple[ReviewRecord, ...] = ()
    guardians: tuple[ChangeReport, ...] = ()
    final_validations: tuple[FinalValidation, ...] = ()
    delivery: GitDelivery | None = None
    artifacts: tuple[Artifact, ...] = ()
    findings: tuple[Finding, ...] = ()
    blockers: tuple[str, ...] = ()
