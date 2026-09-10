from orqalis.domain.errors import ConflictError
from orqalis.domain.run import RunState, UIPhase

_SEQUENCE = (
    RunState.RECEIVED,
    RunState.CONTEXT_SYNC,
    RunState.ANALYZING,
    RunState.GOAL_DEFINED,
    RunState.PLANNED,
    RunState.EXECUTING,
    RunState.INTEGRATING,
    RunState.TESTING,
    RunState.REVIEWING,
    RunState.CHANGE_GUARD,
    RunState.DOCUMENTING,
    RunState.DELIVERY_VALIDATION,
    RunState.COMMITTING,
    RunState.PUSHING,
    RunState.MEMORY_FINALIZATION,
    RunState.COMPLETED,
)
TERMINAL = frozenset({RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED})
TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    state: frozenset({next_state})
    for state, next_state in zip(_SEQUENCE, _SEQUENCE[1:], strict=False)
}
TRANSITIONS[RunState.REVIEWING] |= {RunState.REPAIR_PLANNING}
TRANSITIONS[RunState.CHANGE_GUARD] |= {RunState.REPAIR_PLANNING}
TRANSITIONS[RunState.REPAIR_PLANNING] = frozenset({RunState.EXECUTING})
TRANSITIONS[RunState.COMMITTING] |= {RunState.MEMORY_FINALIZATION}

PHASES = {
    RunState.RECEIVED: UIPhase.CONTEXT,
    RunState.CONTEXT_SYNC: UIPhase.CONTEXT,
    RunState.ANALYZING: UIPhase.GOAL,
    RunState.GOAL_DEFINED: UIPhase.GOAL,
    RunState.PLANNED: UIPhase.PLAN,
    RunState.EXECUTING: UIPhase.IMPLEMENT,
    RunState.INTEGRATING: UIPhase.IMPLEMENT,
    RunState.TESTING: UIPhase.TEST,
    RunState.REVIEWING: UIPhase.REVIEW,
    RunState.REPAIR_PLANNING: UIPhase.REPAIR,
    RunState.CHANGE_GUARD: UIPhase.REVIEW,
    RunState.DOCUMENTING: UIPhase.DOCS,
    RunState.DELIVERY_VALIDATION: UIPhase.DELIVER,
    RunState.COMMITTING: UIPhase.DELIVER,
    RunState.PUSHING: UIPhase.DELIVER,
    RunState.MEMORY_FINALIZATION: UIPhase.DELIVER,
    RunState.COMPLETED: UIPhase.DELIVER,
}


def validate_transition(
    previous: RunState, target: RunState, resume_state: RunState | None = None
) -> None:
    if previous in TERMINAL:
        raise ConflictError("Terminal runs cannot transition")
    if target in {
        RunState.CANCELLED,
        RunState.FAILED,
        RunState.PAUSED,
        RunState.BLOCKED,
        RunState.HUMAN_REVIEW_REQUIRED,
    }:
        if previous == target:
            raise ConflictError("State already active")
        return
    if previous in {RunState.PAUSED, RunState.BLOCKED, RunState.HUMAN_REVIEW_REQUIRED}:
        if target != resume_state:
            raise ConflictError("Resume must return to the persisted prior state")
        return
    if target not in TRANSITIONS.get(previous, frozenset()):
        raise ConflictError(f"Invalid transition: {previous} -> {target}")
