from pathlib import Path
from uuid import uuid4

import pytest

from orqalis.config.settings import Settings
from orqalis.domain.base import utc_now
from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.events import Event, EventPayload, EventType
from orqalis.observability.activity import skill_activity
from orqalis.sdk import Orqalis


def test_skill_load_summary_counts_events_and_keeps_historical_actors() -> None:
    actor = uuid4()
    event = Event(
        project_id=uuid4(),
        run_id=uuid4(),
        sequence=1,
        event_type=EventType.SKILL_LOADED,
        occurred_at=utc_now(),
        actor_session_id=actor,
        idempotency_key="load",
        payload=EventPayload(skill_refs=("python-edit@1.0.0", "python-edit@1.0.0")),
    )
    again = event.model_copy(update={"sequence": 2, "id": uuid4()})
    unrelated = event.model_copy(update={"event_type": EventType.PROVIDER_INVOCATION_STARTED})
    activity = skill_activity((event, again, unrelated))
    assert len(activity) == 1
    assert activity[0].load_count == 2
    assert activity[0].actor_session_ids == (actor,)
    assert activity[0].ref == "python-edit@1.0.0"
    assert skill_activity(()) == ()


def test_skill_catalog_rejects_sensitive_metadata_without_loading_instructions(
    tmp_path: Path,
) -> None:
    skill = tmp_path / "private-skill"
    skill.mkdir()
    (skill / "skill.toml").write_text(
        'id = "private-skill"\nversion = "1.0.0"\n'
        'description = "api_key=do-not-display"\ncapabilities = ["test"]\n'
    )
    sdk = Orqalis(settings=Settings(skill_roots=(tmp_path,)))
    try:
        with pytest.raises(PolicyDeniedError, match="sensitive metadata"):
            sdk.list_skills()
    finally:
        sdk.close()
