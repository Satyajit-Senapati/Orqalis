import asyncio
import json

import httpx
import pytest
from pydantic import SecretStr

from orqalis.domain.capabilities import ToolName
from orqalis.domain.provider import ProviderErrorCode, ToolDefinition
from orqalis.providers.anthropic import AnthropicProvider
from orqalis.providers.errors import ProviderError
from orqalis.providers.external_cli import CLIInvocation, ExternalCLIProvider
from tests.unit.test_providers import SCHEMA, request


def test_anthropic_structured_output_usage_and_private_block_discard() -> None:
    def handle(req: httpx.Request) -> httpx.Response:
        assert str(req.url) == "https://api.anthropic.com/v1/messages"
        assert req.headers["anthropic-version"] == "2023-06-01"
        body = json.loads(req.content)
        assert body["output_config"]["format"]["schema"] == SCHEMA
        assert body["model"] == "configured-model"
        return httpx.Response(
            200,
            json={
                "stop_reason": "end_turn",
                "content": [
                    {
                        "type": "thinking",
                        "thinking": "private-thoughts",
                        "signature": "private-signature",
                    },
                    {"type": "text", "text": '{"summary":"Verified source"}'},
                ],
                "usage": {
                    "input_tokens": 25,
                    "cache_creation_input_tokens": 5,
                    "cache_read_input_tokens": 40,
                    "output_tokens": 9,
                },
            },
        )

    provider = AnthropicProvider(
        "configured-model", SecretStr("fixture-key"), httpx.MockTransport(handle)
    )
    result = asyncio.run(provider.execute(request()))
    assert result.output == {"summary": "Verified source"}
    assert result.usage.input_tokens == 70 and result.usage.cached_input_tokens == 40
    assert result.usage.estimated_cost_usd is None
    assert "private" not in result.model_dump_json()


@pytest.mark.parametrize("invalid_path", [False, True])
def test_anthropic_tool_round_and_local_schema_constraints(invalid_path: bool) -> None:
    tool = ToolDefinition(
        name=ToolName.FILE_READ,
        description="Read source",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "minLength": 1}},
            "required": ["path"],
            "additionalProperties": False,
        },
    )
    original = request().model_copy(update={"allowed_tools": (tool,)})

    def handle(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        field = body["tools"][0]["input_schema"]["properties"]["path"]
        assert "minLength" not in field and "minLength" in field["description"]
        return httpx.Response(
            200,
            json={
                "stop_reason": "tool_use",
                "content": [
                    {"type": "text", "text": "Reading the source"},
                    {
                        "type": "tool_use",
                        "id": "call-1",
                        "name": "filesystem_read",
                        "input": {"path": "" if invalid_path else "main.py"},
                    },
                ],
            },
        )

    provider = AnthropicProvider(
        "configured-model", SecretStr("fixture-key"), httpx.MockTransport(handle)
    )
    if invalid_path:
        with pytest.raises(ProviderError) as raised:
            asyncio.run(provider.execute(original))
        assert raised.value.error_code == ProviderErrorCode.INVALID_OUTPUT
        return
    result = asyncio.run(provider.execute(original))
    assert result.output is None and result.tool_calls[0].name == ToolName.FILE_READ


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("auth", ProviderErrorCode.AUTHENTICATION),
        ("rate", ProviderErrorCode.RATE_LIMIT),
        ("timeout", ProviderErrorCode.TIMEOUT),
        ("refusal", ProviderErrorCode.REFUSED),
        ("truncated", ProviderErrorCode.INVALID_OUTPUT),
        ("secret", ProviderErrorCode.INVALID_OUTPUT),
        ("unauthorized", ProviderErrorCode.INVALID_OUTPUT),
    ],
)
def test_anthropic_normalizes_failures(mode: str, expected: ProviderErrorCode) -> None:
    def handle(req: httpx.Request) -> httpx.Response:
        if mode == "timeout":
            raise httpx.ReadTimeout("private credential diagnostics", request=req)
        if mode in {"auth", "rate"}:
            return httpx.Response(401 if mode == "auth" else 429, text="private credentials")
        payload = {
            "stop_reason": "refusal"
            if mode == "refusal"
            else "max_tokens"
            if mode == "truncated"
            else "tool_use"
            if mode == "unauthorized"
            else "end_turn",
            "content": [{"type": "tool_use", "id": "x", "name": "shell_run", "input": {}}]
            if mode == "unauthorized"
            else [{"type": "text", "text": '{"summary":"api_key=unsafe-value"}'}],
        }
        return httpx.Response(200, json=payload)

    provider = AnthropicProvider(
        "configured-model", SecretStr("fixture-key"), httpx.MockTransport(handle)
    )
    with pytest.raises(ProviderError) as raised:
        asyncio.run(provider.execute(request()))
    assert raised.value.error_code == expected
    assert "private" not in str(raised.value)


def test_external_cli_contract_and_unavailable_default() -> None:
    class Transport:
        async def invoke(self, invocation: CLIInvocation) -> bytes:
            assert invocation.command == ("approved-wrapper",)
            assert "request_json=SecretStr" in repr(invocation)
            assert "run_id" in json.loads(invocation.request_json.get_secret_value())
            return b'{"output":{"summary":"CLI inspected source"}}'

    adapter = ExternalCLIProvider("local-model", ("approved-wrapper",), Transport())
    assert asyncio.run(adapter.execute(request())).output == {"summary": "CLI inspected source"}
    with pytest.raises(ProviderError):
        asyncio.run(ExternalCLIProvider("local-model", ("approved-wrapper",)).execute(request()))


def test_multiple_provider_configuration_requires_explicit_model_and_key() -> None:
    from orqalis.config.settings import Settings
    from orqalis.providers.configuration import configured_providers

    settings = Settings(
        openai_api_key=SecretStr("fixture-key"),
        openai_model="explicit-openai",
        anthropic_api_key=SecretStr("fixture-key"),
        anthropic_model="explicit-claude",
    )
    assert {p.descriptor.id for p in configured_providers(settings)} == {"openai", "anthropic"}
    assert configured_providers(Settings(openai_api_key=None, anthropic_api_key=None)) == ()
