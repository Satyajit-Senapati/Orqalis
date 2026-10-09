"""Agent Skills frontmatter adapted to Orqalis's explicit capability policy.

The interchange format is documented at https://agentskills.io/specification.
Instructions remain data; tool declarations never grant execution permissions.
"""

import re
from pathlib import Path

import yaml
from yaml.nodes import MappingNode, ScalarNode
from yaml.tokens import (
    AliasToken,
    AnchorToken,
    BlockEndToken,
    BlockMappingStartToken,
    FlowMappingEndToken,
    FlowMappingStartToken,
)

from orqalis.domain.capabilities import SkillMetadata, ToolName
from orqalis.domain.errors import InputError

_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
_TOOL_ALIASES = {
    "Read": ToolName.FILE_READ,
    "Write": ToolName.FILE_WRITE,
    "Edit": ToolName.FILE_WRITE,
    "Bash": ToolName.SHELL_RUN,
}


def _strings(node: MappingNode) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in node.value:
        if (
            not isinstance(key, ScalarNode)
            or key.tag != "tag:yaml.org,2002:str"
            or not isinstance(value, ScalarNode)
            or value.tag != "tag:yaml.org,2002:str"
            or key.value in result
        ):
            raise InputError("Skill metadata must contain unique string keys and string values")
        result[key.value] = value.value
    return result


def parse_skill_markdown(raw: str, directory: Path) -> tuple[SkillMetadata, str]:
    """Parse bounded, non-executable YAML without aliases or implicit coercion."""
    if not raw.startswith("---\n"):
        raise InputError("SKILL.md requires YAML frontmatter")
    header, separator, body = raw[4:].partition("\n---\n")
    if not separator and raw.endswith("\n---"):
        header, separator, body = raw[4:-4], "---", ""
    if not separator or len(header) > 16_000:
        raise InputError("Skill frontmatter is missing or exceeds 16000 characters")
    try:
        depth = 0
        for token in yaml.scan(header):
            if isinstance(token, AliasToken | AnchorToken):
                raise InputError("Skill frontmatter cannot contain YAML anchors or aliases")
            if isinstance(token, BlockMappingStartToken | FlowMappingStartToken):
                depth += 1
                if depth > 2:
                    raise InputError("Skill frontmatter nesting exceeds the supported format")
            elif isinstance(token, BlockEndToken | FlowMappingEndToken):
                depth -= 1
        node = yaml.compose(header, Loader=yaml.SafeLoader)
    except (yaml.YAMLError, RecursionError):
        raise InputError("Invalid skill YAML frontmatter") from None
    if not isinstance(node, MappingNode) or node.tag != "tag:yaml.org,2002:map":
        raise InputError("Skill frontmatter must be a mapping")
    fields: dict[str, str] = {}
    metadata: dict[str, str] = {}
    seen: set[str] = set()
    for key, value in node.value:
        if (
            not isinstance(key, ScalarNode)
            or key.tag != "tag:yaml.org,2002:str"
            or key.value not in _FIELDS
            or key.value in seen
        ):
            raise InputError("Unsupported or duplicate Agent Skills frontmatter field")
        seen.add(key.value)
        if key.value == "metadata":
            if not isinstance(value, MappingNode) or value.tag != "tag:yaml.org,2002:map":
                raise InputError("Skill metadata must be a string mapping")
            metadata = _strings(value)
        else:
            fields.update(_strings(MappingNode(node.tag, [(key, value)])))
    name, description = fields.get("name", ""), fields.get("description", "")
    if (
        not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
        or len(name) > 64
        or name != directory.name
    ):
        raise InputError("Skill name must match its directory and use lowercase words and hyphens")
    if not description.strip() or len(description) > 1024:
        raise InputError("Skill description must contain 1..1024 characters")
    compatibility = fields.get("compatibility", "")
    if "compatibility" in fields and not 1 <= len(compatibility) <= 500:
        raise InputError("Skill compatibility must contain 1..500 characters")
    # Bare host names are translated only to requirements. Scoped expressions and
    # unknown tools are rejected instead of silently broadening their permissions.
    tools: list[ToolName] = []
    declarations = fields.get("allowed-tools", "").split()
    declarations += metadata.get("orqalis-required-tools", "").replace(",", " ").split()
    for declaration in declarations:
        try:
            tool = (
                _TOOL_ALIASES[declaration]
                if declaration in _TOOL_ALIASES
                else ToolName(declaration)
            )
        except ValueError:
            raise InputError("Skill declares an unsupported tool requirement") from None
        if tool not in tools:
            tools.append(tool)
    version = metadata.get("orqalis-version", "0.0.0")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise InputError("orqalis-version must be a semantic version")
    capabilities = tuple(
        item.strip()
        for item in metadata.get("orqalis-capabilities", name).split(",")
        if item.strip()
    )
    if not capabilities:
        raise InputError("Skill must declare at least one capability")
    return SkillMetadata(
        id=name,
        version=version,
        description=description,
        capabilities=capabilities,
        required_tools=tuple(tools),
        applicable_when=tuple(
            item.strip()
            for item in metadata.get("orqalis-applicable-when", "").split(",")
            if item.strip()
        ),
        constraints=(compatibility,) if compatibility else (),
    ), body.strip()
