import asyncio
from typing import Protocol

from pydantic import Field, SecretStr, ValidationError

from orqalis.domain.base import Contract
from orqalis.domain.provider import (
    ProviderDescriptor,
    ProviderErrorCode,
    ProviderExecutionRequest,
    ProviderExecutionResult,
)
from orqalis.providers.errors import ProviderError
from orqalis.providers.validation import prompt_input, validate_result


class CLIInvocation(Contract):
    """Contract for a host-owned CLI launcher; arguments are fixed by server configuration."""

    command: tuple[str, ...] = Field(min_length=1)
    request_json: SecretStr
    timeout_seconds: float = Field(gt=0)
    max_response_bytes: int = 1_000_000


class CLITransport(Protocol):
    """Launch exactly argv without a shell; send request on stdin, return bounded stdout.

    Implementations must confine environment/workdir, terminate owned descendants on
    timeout/cancellation, keep stderr private, and never retry an uncertain execution.
    Native assistant integrations should use MCP unless such a launcher is configured.
    """

    async def invoke(self, invocation: CLIInvocation) -> bytes: ...


class ExternalCLIProvider:
    def __init__(
        self, model: str, command: tuple[str, ...], transport: CLITransport | None = None
    ) -> None:
        self.descriptor = ProviderDescriptor(
            id="external_cli",
            model=model,
            available=transport is not None,
            capabilities=("structured_output", "tool_calls"),
        )
        self.command, self.transport = command, transport

    async def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        if self.transport is None:
            raise ProviderError(ProviderErrorCode.UNAVAILABLE)
        prompt_input(request)  # Apply privacy and input-budget policy before invoking the launcher.
        invocation = CLIInvocation(
            command=self.command,
            request_json=SecretStr(request.model_dump_json()),
            timeout_seconds=request.budget.timeout_seconds,
        )
        try:
            async with asyncio.timeout(invocation.timeout_seconds):
                raw = await self.transport.invoke(invocation)
            if len(raw) > invocation.max_response_bytes:
                raise ProviderError(ProviderErrorCode.BUDGET)
            return validate_result(request, ProviderExecutionResult.model_validate_json(raw))
        except TimeoutError:
            raise ProviderError(ProviderErrorCode.TIMEOUT) from None
        except (ValidationError, ValueError):
            raise ProviderError(ProviderErrorCode.INVALID_OUTPUT) from None
        except OSError:
            raise ProviderError(ProviderErrorCode.TRANSPORT) from None
