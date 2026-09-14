import asyncio
import copy
import json
from uuid import uuid4

import httpx
import pytest
from jsonschema import Draft202012Validator
from pydantic import JsonValue, SecretStr

from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.capabilities import ToolName
from orqalis.domain.memory import ContextPack, MemoryHealth
from orqalis.domain.provider import ProviderErrorCode, ProviderExecutionRequest, ToolDefinition
from orqalis.domain.task import Task
from orqalis.execution.tool_definitions import ReadFile
from orqalis.providers.errors import ProviderError
from orqalis.providers.openai import OpenAIProvider
from orqalis.providers.openai_schema import openai_schema


def strict_server_schema(schema: JsonValue) -> None:
    if isinstance(schema, dict):
        assert not {"default", "discriminator", "oneOf", "allOf"} & schema.keys()
        if schema.get("type") == "object":
            properties = schema.get("properties")
            assert isinstance(properties, dict)
            assert set(schema["required"]) == set(properties)  # type: ignore[arg-type]
            assert schema["additionalProperties"] is False
        for value in schema.values():
            strict_server_schema(value)
    elif isinstance(schema, list):
        for value in schema:
            strict_server_schema(value)


def execution_request() -> ProviderExecutionRequest:
    project_id = uuid4()
    task = Task(
        run_id=uuid4(),
        description="Define a goal",
        expected_outcome="A contract",
        validation_method="schema",
    )
    return ProviderExecutionRequest(
        invocation_id=uuid4(),
        run_id=task.run_id,
        actor_session_id=uuid4(),
        task_execution_id=uuid4(),
        role=task.preferred_role,
        task=task,
        context=ContextPack(
            project_id=project_id,
            task="Define a goal",
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
        ),
        output_schema=GoalDraft.model_json_schema(),
        allowed_tools=(
            ToolDefinition(
                name=ToolName.FILE_READ,
                description="Read a file",
                parameters=ReadFile.model_json_schema(),
            ),
        ),
    )


def test_strict_schema_adapts_real_goal_and_tools_without_mutating_contract() -> None:
    request = execution_request()
    original = copy.deepcopy(request.output_schema)
    adapted = openai_schema(original)
    strict_server_schema(adapted)
    assert request.output_schema == original
    definitions = adapted["$defs"]
    assert isinstance(definitions, dict)
    file_schema = definitions["FileValidation"]
    assert isinstance(file_schema, dict)
    properties = file_schema["properties"]
    assert isinstance(properties, dict)
    contains = properties["contains"]
    assert isinstance(contains, dict)
    assert {"type": "null"} in contains["anyOf"]  # type: ignore[operator]
    assert (
        adapted["properties"] != original["properties"]
        or adapted["required"] != original["required"]
    )
    assert Draft202012Validator(original).is_valid(
        GoalDraft(
            goal="Keep behavior",
            scope=("main.py",),
            definition_of_done=("Source checked",),
            criteria=(
                CriterionDefinition(
                    key="AC-1",
                    description="File exists",
                    validation_spec=FileValidation(path="main.py"),
                ),
            ),
        ).model_dump(mode="json")
    )


@pytest.mark.parametrize("invalid_result", [False, True])
def test_openai_http_boundary_accepts_strict_schema_but_rechecks_domain_constraints(
    invalid_result: bool,
) -> None:
    proposal = GoalDraft(
        goal="Implement a behavior",
        scope=("main.py",),
        definition_of_done=("Source validated",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="File exists",
                validation_spec=FileValidation(path="main.py"),
            ),
        ),
    ).model_dump(mode="json")
    if invalid_result:
        proposal["goal"] = ""

    def handle(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        schema = body["text"]["format"]["schema"]
        strict_server_schema(schema)
        for tool in body["tools"]:
            strict_server_schema(tool["parameters"])
            assert set(tool["parameters"]["required"]) == {"path", "start_line", "line_count"}
        assert Draft202012Validator(schema).is_valid(proposal)
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(proposal)}],
                    }
                ],
            },
        )

    provider = OpenAIProvider(
        "configured-model", SecretStr("fixture-key"), httpx.MockTransport(handle)
    )
    if invalid_result:
        with pytest.raises(ProviderError) as caught:
            asyncio.run(provider.execute(execution_request()))
        assert caught.value.error_code == ProviderErrorCode.INVALID_OUTPUT
    else:
        result = asyncio.run(provider.execute(execution_request()))
        assert result.output == proposal


def test_strict_schema_rejects_unbounded_objects_and_external_references() -> None:
    with pytest.raises(ProviderError):
        openai_schema({"type": "object", "additionalProperties": {"type": "string"}})
    with pytest.raises(ProviderError):
        openai_schema(
            {"type": "object", "properties": {"data": {"$ref": "https://invalid.example/schema"}}}
        )
