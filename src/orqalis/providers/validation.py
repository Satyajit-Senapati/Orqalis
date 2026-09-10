import json

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import JsonValue

from orqalis.domain.provider import (
    ProviderErrorCode,
    ProviderExecutionRequest,
    ProviderExecutionResult,
)
from orqalis.providers.errors import ProviderError
from orqalis.security.redaction import safe_diagnostic

_PRIVATE_KEYS = {"chain_of_thought", "reasoning", "scratchpad", "analysis", "thinking"}


def check_schema(schema: dict[str, JsonValue]) -> None:
    # Schema references never trigger network/file resolution.
    def inspect(value: JsonValue) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"$ref", "$dynamicRef"} and (
                    not isinstance(item, str) or not item.startswith("#")
                ):
                    raise ProviderError(ProviderErrorCode.INVALID_OUTPUT)
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)

    inspect(schema)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError:
        raise ProviderError(ProviderErrorCode.INVALID_OUTPUT) from None


def safe_value(value: JsonValue) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in _PRIVATE_KEYS or safe_diagnostic(key) != key:
                raise ProviderError(ProviderErrorCode.INVALID_OUTPUT)
            safe_value(item)
    elif isinstance(value, list):
        for item in value:
            safe_value(item)
    elif isinstance(value, str) and safe_diagnostic(value) != value:
        # Reject, rather than alter, executable structured content.
        raise ProviderError(ProviderErrorCode.INVALID_OUTPUT)


def validate_result(
    request: ProviderExecutionRequest, result: ProviderExecutionResult
) -> ProviderExecutionResult:
    if len(result.model_dump_json()) > 1_000_000:
        raise ProviderError(ProviderErrorCode.BUDGET)
    safe_value(result.model_dump(mode="json"))
    if result.output is not None:
        check_schema(request.output_schema)
        if not Draft202012Validator(request.output_schema).is_valid(result.output):
            raise ProviderError(ProviderErrorCode.INVALID_OUTPUT)
    else:
        definitions = {tool.name: tool for tool in request.allowed_tools}
        for call in result.tool_calls:
            if call.name not in definitions:
                raise ProviderError(ProviderErrorCode.INVALID_OUTPUT)
            schema = definitions[call.name].parameters
            check_schema(schema)
            if not Draft202012Validator(schema).is_valid(call.arguments):
                raise ProviderError(ProviderErrorCode.INVALID_OUTPUT)
    return result


def prompt_input(request: ProviderExecutionRequest) -> str:
    content = request.model_dump(mode="json", exclude={"output_schema", "allowed_tools", "budget"})
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True)
    if len(encoded) > request.budget.max_input_chars:
        raise ProviderError(ProviderErrorCode.BUDGET)
    # Input may contain code; secrets/private diagnostic markers cannot leave this boundary.
    safe_value(content)
    return encoded
