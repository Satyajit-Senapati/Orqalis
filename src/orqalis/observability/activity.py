"""Read-only operational summaries from canonical events."""

from collections.abc import Sequence

from orqalis.domain.events import Event, EventType
from orqalis.domain.telemetry import SkillActivity


def skill_activity(events: Sequence[Event]) -> tuple[SkillActivity, ...]:
    grouped: dict[str, list[Event]] = {}
    for event in events:
        if event.event_type == EventType.SKILL_LOADED:
            for ref in dict.fromkeys(event.payload.skill_refs):
                grouped.setdefault(ref, []).append(event)
    return tuple(
        SkillActivity(
            ref=ref,
            load_count=len(items),
            actor_session_ids=tuple(
                dict.fromkeys(event.actor_session_id for event in items if event.actor_session_id)
            ),
            last_loaded_at=max(event.occurred_at for event in items),
        )
        for ref, items in sorted(grouped.items())
    )
