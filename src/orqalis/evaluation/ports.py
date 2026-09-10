from typing import Protocol

from orqalis.domain.acceptance import GoalDraft, ValidationSpec
from orqalis.domain.artifact import ValidationObservation
from orqalis.domain.memory import ContextPack


class RequirementsAgent(Protocol):
    def define_goal(self, request: str, context: ContextPack) -> GoalDraft: ...


class Evaluator(Protocol):
    def evaluate(self, spec: ValidationSpec) -> ValidationObservation: ...
