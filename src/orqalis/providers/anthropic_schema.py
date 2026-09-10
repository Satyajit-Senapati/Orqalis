import json

from pydantic import JsonValue

from orqalis.domain.provider import ProviderErrorCode
from orqalis.providers.errors import ProviderError
from orqalis.providers.validation import check_schema

_CONSTRAINTS = {
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "maxItems",
    "uniqueItems",
    "pattern",
}


def anthropic_schema(schema: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Adapt transport grammar only; validate every result against the original contract."""
    check_schema(schema)

    def visit(node: dict[str, JsonValue]) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {}
        constraints = {}
        for key, value in node.items():
            if key in _CONSTRAINTS or (key == "minItems" and value not in (0, 1)):
                constraints[key] = value
            elif key in {"properties", "$defs", "definitions", "patternProperties"} and isinstance(
                value, dict
            ):
                result[key] = {
                    name: visit(child) if isinstance(child, dict) else child
                    for name, child in value.items()
                }
            elif key in {"anyOf", "allOf", "oneOf", "prefixItems"} and isinstance(value, list):
                result["anyOf" if key == "oneOf" else key] = [
                    visit(child) if isinstance(child, dict) else child for child in value
                ]
            elif key == "discriminator":
                continue
            elif isinstance(value, dict):
                result[key] = visit(value)
            else:
                result[key] = value
        if result.get("type") == "object":
            if isinstance(result.get("additionalProperties"), dict):
                raise ProviderError(ProviderErrorCode.INVALID_OUTPUT)
            result["additionalProperties"] = False
        if constraints:
            result["description"] = (
                str(result.get("description", ""))
                + " Required constraints: "
                + json.dumps(constraints)
            ).strip()
        return result

    return visit(schema)
