from datetime import datetime

from orqalis.domain.acceptance import AcceptanceCriterion
from orqalis.domain.artifact import Evidence
from orqalis.domain.base import Contract
from orqalis.domain.task import TaskStatus
from orqalis.domain.timing import TimingBreakdown


class AcceptanceView(Contract):
    criteria: tuple[AcceptanceCriterion, ...]
    evidence: tuple[Evidence, ...]


class RunMetrics(Contract):
    timing: TimingBreakdown
    task_counts: dict[TaskStatus, int]
    plan_completion: float
    server_time: datetime
