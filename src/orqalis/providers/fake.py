from collections.abc import Callable

from orqalis.domain.provider import (
    ProviderDescriptor,
    ProviderExecutionRequest,
    ProviderExecutionResult,
)
from orqalis.providers.validation import validate_result


class FakeProvider:
    """Explicit deterministic fixture backend, never selected as a silent fallback."""

    def __init__(
        self,
        respond: Callable[[ProviderExecutionRequest], ProviderExecutionResult],
        provider_id: str = "fixture",
    ) -> None:
        self.descriptor = ProviderDescriptor(
            id=provider_id,
            model="deterministic-fixture",
            capabilities=("structured_output", "tool_calls"),
            auto_selectable=False,
        )
        self.respond = respond
        self.calls = 0

    async def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        self.calls += 1
        return validate_result(request, self.respond(request))
