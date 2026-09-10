import asyncio
import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from pydantic import JsonValue, SecretStr

from orqalis.agents.roles import effective_tools
from orqalis.agents.routing import CapabilityRouter
from orqalis.domain.agent import AgentRole
from orqalis.domain.capabilities import PermissionProfile, ToolName
from orqalis.domain.errors import ConflictError, InputError, PolicyDeniedError
from orqalis.domain.memory import ContextPack, MemoryHealth
from orqalis.domain.provider import (
    ProviderErrorCode,
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ToolDefinition,
)
from orqalis.domain.task import Task
from orqalis.providers.errors import ProviderError
from orqalis.providers.fake import FakeProvider
from orqalis.providers.openai import OpenAIProvider
from orqalis.providers.validation import check_schema
from orqalis.skills.registry import SkillRegistry

SCHEMA: dict[str, JsonValue] = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
    "additionalProperties": False,
}


def context_pack() -> ContextPack:
    project_id = uuid4()
    return ContextPack(
        project_id=project_id,
        task="Inspect a fixture",
        items=(),
        relevant_files=(),
        freshness=MemoryHealth(
            project_id=project_id,
            indexed_commit="abc",
            current_commit="abc",
            fresh=True,
            dirty_paths=(),
            active_items=0,
        ),
        confidence=1,
        targeted_inspection_paths=(),
        requires_inspection=False,
        size_chars=0,
    )


def request() -> ProviderExecutionRequest:
    task = Task(
        run_id=uuid4(),
        description="Inspect a fixture",
        expected_outcome="Summary",
        validation_method="file assertion",
    )
    return ProviderExecutionRequest(
        invocation_id=uuid4(),
        run_id=task.run_id,
        actor_session_id=uuid4(),
        task_execution_id=uuid4(),
        role=task.preferred_role,
        task=task,
        context=context_pack(),
        output_schema=SCHEMA,
    )


def test_openai_normalizes_only_public_output_and_usage() -> None:
    def handle(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        assert body["store"] is False
        assert body["text"]["format"]["schema"] == SCHEMA
        assert body["model"] == "configured-model"
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {"type": "reasoning", "private": "not-public"},
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": '{"summary":"Inspected fixture"}'}
                        ],
                    },
                ],
                "usage": {
                    "input_tokens": 25,
                    "output_tokens": 10,
                    "input_tokens_details": {"cached_tokens": 5},
                },
            },
        )

    provider = OpenAIProvider(
        "configured-model", SecretStr("fixture-key"), httpx.MockTransport(handle)
    )
    result = asyncio.run(provider.execute(request()))
    assert result.output == {"summary": "Inspected fixture"}
    assert result.usage.cached_input_tokens == 5
    assert result.usage.estimated_cost_usd is None
    assert "not-public" not in result.model_dump_json()


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"status": "incomplete", "output": []}, ProviderErrorCode.INVALID_OUTPUT),
        (
            {
                "status": "completed",
                "output": [{"type": "message", "content": [{"type": "refusal"}]}],
            },
            ProviderErrorCode.REFUSED,
        ),
        (
            {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"summary":"sk-privatecredential12345678"}',
                            }
                        ],
                    }
                ],
            },
            ProviderErrorCode.INVALID_OUTPUT,
        ),
        (
            {
                "status": "completed",
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "x",
                        "name": "filesystem_write",
                        "arguments": "{}",
                    }
                ],
            },
            ProviderErrorCode.INVALID_OUTPUT,
        ),
    ],
)
def test_openai_rejects_incomplete_private_or_unauthorized_outputs(
    payload: dict[str, object],
    code: ProviderErrorCode,
) -> None:
    provider = OpenAIProvider(
        "configured-model",
        SecretStr("fixture-key"),
        httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
    )
    with pytest.raises(ProviderError) as caught:
        asyncio.run(provider.execute(request()))
    assert caught.value.error_code == code
    assert "privatecredential" not in str(caught.value)


def test_openai_error_and_tool_normalization() -> None:
    provider = OpenAIProvider(
        "configured-model",
        SecretStr("fixture-key"),
        httpx.MockTransport(lambda _: httpx.Response(429, text="secret provider prompt")),
    )
    with pytest.raises(ProviderError) as caught:
        asyncio.run(provider.execute(request()))
    assert caught.value.error_code == ProviderErrorCode.RATE_LIMIT
    assert "secret provider prompt" not in str(caught.value)
    allowed = ToolDefinition(
        name=ToolName.FILE_READ,
        description="Read a scoped file",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    )
    provider = OpenAIProvider(
        "configured-model",
        SecretStr("fixture-key"),
        httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "c1",
                            "name": "filesystem_read",
                            "arguments": '{"path":"main.py"}',
                        }
                    ],
                },
            )
        ),
    )
    result = asyncio.run(
        provider.execute(request().model_copy(update={"allowed_tools": (allowed,)}))
    )
    assert result.tool_calls[0].name == ToolName.FILE_READ
    assert result.output is None


def test_skill_selection_capabilities_permissions_versions_and_change_detection(
    tmp_path: Path,
) -> None:
    for version in ("1.0.0", "2.0.0"):
        directory = tmp_path / version
        directory.mkdir()
        (directory / "skill.toml").write_text(
            f'id = "python"\nversion = "{version}"\ndescription = "Python"\n'
            'capabilities = ["python"]\napplicable_when = ["python"]\n'
            'required_tools = ["filesystem.write"]\n'
        )
        (directory / "instructions.md").write_text("Use explicit types.\n")
    registry = SkillRegistry((tmp_path,))
    selected = registry.select(("python",), (ToolName.FILE_WRITE,), ("python",))
    assert selected[0].metadata.version == "2.0.0"
    assert registry.select((), ()) == ()
    assert (
        registry.select(("python",), (ToolName.FILE_WRITE,), ("python",), pins={"python": "1.0.0"})[
            0
        ].metadata.version
        == "1.0.0"
    )
    with pytest.raises(InputError):
        registry.select(("python",), (ToolName.FILE_READ,), ("python",))
    with pytest.raises(InputError):
        registry.select(("python",), (ToolName.FILE_WRITE,), ("javascript",))
    path = tmp_path / "2.0.0" / "skill.toml"
    path.write_text(path.read_text().replace('description = "Python"', 'description = "Changed"'))
    with pytest.raises(ConflictError):
        registry.load(selected[0].metadata)


def test_router_reviewer_cannot_gain_write_access_from_skill(tmp_path: Path) -> None:
    fake = FakeProvider(lambda _: ProviderExecutionResult(output={"summary": "Reviewed"}))
    router = CapabilityRouter(SkillRegistry((tmp_path,)), (fake,))
    req = request()
    task = req.task.model_copy(update={"preferred_role": AgentRole.REVIEWER})
    policy = PermissionProfile(allowed_tools=tuple(ToolName))
    assert ToolName.FILE_WRITE not in effective_tools(AgentRole.REVIEWER, policy)
    tool = ToolDefinition(
        name=ToolName.FILE_WRITE, description="write", parameters={"type": "object"}
    )
    with pytest.raises(PolicyDeniedError):
        router.prepare(
            task,
            req.context,
            req.invocation_id,
            req.actor_session_id,
            req.task_execution_id,
            "fixture",
            policy,
            SCHEMA,
            (tool,),
        )
    with pytest.raises(ProviderError):
        check_schema({"$ref": "https://unsafe.invalid/schema"})
