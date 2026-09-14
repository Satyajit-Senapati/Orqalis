"""OpenAI strict transport grammar; the original schema remains the result contract."""

import json

from pydantic import JsonValue

from orqalis.domain.provider import ProviderErrorCode
from orqalis.providers.errors import ProviderError
from orqalis.providers.validation import check_schema

_LOCAL_CONSTRAINTS = {
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "minItems",
    "maxItems",
    "uniqueItems",
}
_UNSUPPORTED = {
    "allOf",
    "not",
    "dependentRequired",
    "dependentSchemas",
    "if",
    "then",
    "else",
    "patternProperties",
    "prefixItems",
}


def openai_schema(schema: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Require explicit object fields without weakening local acceptance validation.

    Defaults remain instructions for the model, not nullable substitutions. Existing
    nullable unions are retained. Non-null domain fields never acquire null permission.
    """
    check_schema(schema)
    if schema.get("type") != "object":
        raise ProviderError(ProviderErrorCode.INVALID_OUTPUT)

    def visit(node: dict[str, JsonValue]) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {}
        constraints: dict[str, JsonValue] = {}
        for key, value in node.items():
            if key in _UNSUPPORTED:
                raise ProviderError(ProviderErrorCode.INVALID_OUTPUT)
            if key in _LOCAL_CONSTRAINTS or key == "default":
                constraints[key] = value
            elif key == "discriminator":
                continue
            elif key == "const":
                result["enum"] = [value]
            elif key in {"properties", "$defs", "definitions"} and isinstance(value, dict):
                result[key] = {
                    name: visit(child) if isinstance(child, dict) else child
                    for name, child in value.items()
                }
            elif key in {"anyOf", "oneOf"} and isinstance(value, list):
                result["anyOf"] = [
                    visit(child) if isinstance(child, dict) else child for child in value
                ]
            elif isinstance(value, dict):
                result[key] = visit(value)
            else:
                result[key] = value
        if result.get("type") == "object":
            if result.get("additionalProperties") not in (None, False):
                raise ProviderError(ProviderErrorCode.INVALID_OUTPUT)
            properties = result.get("properties", {})
            if not isinstance(properties, dict):
                raise ProviderError(ProviderErrorCode.INVALID_OUTPUT)
            result["properties"] = properties
            result["required"] = list(properties)
            result["additionalProperties"] = False
        if constraints:
            result["description"] = (
                str(result.get("description", ""))
                + " Domain constraints/defaults: "
                + json.dumps(constraints)
            ).strip()
        return result

    return visit(schema)
