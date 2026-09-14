import pytest
from jsonschema import Draft202012Validator

from orqalis.agents.roles import provider_output_schema, role_definition
from orqalis.domain.agent import AgentRole
from orqalis.domain.capabilities import ToolName
from orqalis.domain.errors import PolicyDeniedError


def test_provider_roles_have_distinct_validated_output_contracts() -> None:
    goal = {
        "goal": "Fix a bug",
        "scope": ["src"],
        "definition_of_done": ["Tests pass"],
        "criteria": [
            {
                "key": "AC-1",
                "description": "Bug is fixed",
                "validation_spec": {"kind": "review", "instructions": "Inspect evidence"},
            }
        ],
    }
    work = {"summary": "Implemented", "completed": True, "artifact_paths": ["src/fix.py"]}
    review = {
        "overall": "FAIL",
        "criteria": [],
        "blocking_findings": ["Missing evidence"],
        "non_blocking_findings": [],
    }
    samples = (
        (AgentRole.REQUIREMENTS, goal),
        (AgentRole.ARCHITECT, work),
        (AgentRole.PLANNER, work),
        (AgentRole.DEVELOPER, work),
        (AgentRole.REPAIR, work),
        (AgentRole.REVIEWER, review),
    )
    for role, output in samples:
        validator = Draft202012Validator(provider_output_schema(role))
        assert validator.is_valid(output), role
    assert not Draft202012Validator(provider_output_schema(AgentRole.REVIEWER)).is_valid(work)
    assert not Draft202012Validator(provider_output_schema(AgentRole.DEVELOPER)).is_valid(review)


def test_service_roles_cannot_use_provider_worker_output_contract() -> None:
    for role in (
        AgentRole.TESTER,
        AgentRole.CHANGE_GUARDIAN,
        AgentRole.DOCUMENTATION,
        AgentRole.GITOPS,
        AgentRole.MEMORY_CURATOR,
    ):
        with pytest.raises(PolicyDeniedError):
            provider_output_schema(role)


def test_role_catalog_exposes_authority_and_output_boundaries() -> None:
    definitions = {role: role_definition(role) for role in AgentRole}
    assert all(definition.authority_boundaries for definition in definitions.values())
    assert all(definition.output_contract != "unspecified" for definition in definitions.values())
    assert definitions[AgentRole.REVIEWER].can_approve_acceptance
    assert ToolName.FILE_WRITE not in definitions[AgentRole.REVIEWER].permissions.allowed_tools
    guardian_tools = definitions[AgentRole.CHANGE_GUARDIAN].permissions.allowed_tools
    assert ToolName.FILE_WRITE not in guardian_tools
    assert ToolName.FILE_WRITE in definitions[AgentRole.DEVELOPER].permissions.allowed_tools
