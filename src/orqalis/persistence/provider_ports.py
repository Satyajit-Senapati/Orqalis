from typing import Protocol
from uuid import UUID

from orqalis.domain.provider import ProviderExecution


class ProviderRepository(Protocol):
    def get(self, invocation_id: UUID) -> ProviderExecution | None: ...
    def save(self, invocation: ProviderExecution) -> None: ...
    def list(self, run_id: UUID) -> tuple[ProviderExecution, ...]: ...
