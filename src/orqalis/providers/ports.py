from typing import Protocol

from orqalis.domain.provider import (
    ProviderDescriptor,
    ProviderExecutionRequest,
    ProviderExecutionResult,
)


class AgentProvider(Protocol):
    @property
    def descriptor(self) -> ProviderDescriptor: ...
    async def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult: ...
