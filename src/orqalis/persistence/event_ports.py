from typing import Protocol
from uuid import UUID

from orqalis.domain.events import Event, EventDraft


class EventRepository(Protocol):
    def append(self, run_id: UUID, draft: EventDraft) -> Event: ...
    def list(self, run_id: UUID, after: int = 0) -> tuple[Event, ...]: ...
    def by_key(self, run_id: UUID, key: str) -> Event | None: ...
