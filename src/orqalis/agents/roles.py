from typing import cast

from pydantic import JsonValue

from orqalis.domain.acceptance import GoalDraft
from orqalis.domain.agent import AgentRole
from orqalis.domain.base import Contract
from orqalis.domain.capabilities import PermissionProfile, RoleDefinition, ToolName
from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.execution import ReviewResult, WorkerResult

_READ = (ToolName.FILE_READ, ToolName.GIT_DIFF, ToolName.MEMORY_QUERY)
_WRITE = (*_READ, ToolName.FILE_WRITE, ToolName.TEST_RUN)
_RESPONSIBILITIES = {
    AgentRole.REQUIREMENTS: (
        "Define an explicit goal and evidence-backed criteria",
        ("requirements",),
    ),
    AgentRole.ARCHITECT: ("Assess architectural impact and compatibility", ("architecture",)),
    AgentRole.PLANNER: (
        "Propose a dependency-aware plan; never change workflow state",
        ("planning",),
    ),
    AgentRole.DEVELOPER: (
        "Implement scoped changes in the assigned workspace",
        ("implementation",),
    ),
    AgentRole.TESTER: ("Add and run deterministic checks", ("validation",)),
    AgentRole.REVIEWER: ("Review acceptance using observed evidence", ("acceptance_review",)),
    AgentRole.CHANGE_GUARDIAN: ("Independently inspect diff scope and safety", ("scope_review",)),
    AgentRole.REPAIR: ("Diagnose failed criteria and propose targeted repairs", ("diagnosis",)),
    AgentRole.DOCUMENTATION: ("Document the accepted implementation and diff", ("documentation",)),
    AgentRole.GITOPS: (
        "Prepare delivery metadata for the gated Git service",
        ("delivery_metadata",),
    ),
    AgentRole.MEMORY_CURATOR: ("Propose durable source-backed knowledge", ("memory_curation",)),
}

# These describe each role's authority in addition to tool permissions. The
# Orchestrator remains the sole owner of workflow transitions and delivery gates.
_ROLE_CONTRACTS: dict[AgentRole, tuple[str, tuple[str, ...]]] = {
    AgentRole.REQUIREMENTS: (
        "goal_draft",
        ("Propose a goal and criteria; only the Orchestrator can accept a goal version.",),
    ),
    AgentRole.ARCHITECT: (
        "worker_result",
        ("Propose architectural findings; do not change workflow state.",),
    ),
    AgentRole.PLANNER: (
        "worker_result",
        ("Propose task dependencies; only the Orchestrator can install a plan.",),
    ),
    AgentRole.DEVELOPER: (
        "worker_result",
        ("Edit the assigned workspace; do not approve acceptance or deliver Git changes.",),
    ),
    AgentRole.TESTER: (
        "validation_evidence",
        ("Produce deterministic validation evidence; do not decide acceptance.",),
    ),
    AgentRole.REVIEWER: (
        "review_result",
        ("Propose an evidence-backed review; do not edit implementation files.",),
    ),
    AgentRole.CHANGE_GUARDIAN: (
        "change_findings",
        ("Independently inspect scope and safety; do not edit the reviewed diff.",),
    ),
    AgentRole.REPAIR: (
        "worker_result",
        ("Propose targeted repairs; do not reset the run or its acceptance criteria.",),
    ),
    AgentRole.DOCUMENTATION: (
        "documentation_changes",
        ("Edit documentation for accepted behavior within the assigned workspace.",),
    ),
    AgentRole.GITOPS: (
        "delivery_metadata",
        ("Prepare commit metadata; only the gated Git service may commit or push.",),
    ),
    AgentRole.MEMORY_CURATOR: (
        "memory_proposal",
        ("Propose source-backed knowledge; only the memory service may promote it.",),
    ),
}

_PROVIDER_OUTPUT_MODELS: dict[AgentRole, type[Contract]] = {
    AgentRole.REQUIREMENTS: GoalDraft,
    AgentRole.ARCHITECT: WorkerResult,
    AgentRole.PLANNER: WorkerResult,
    AgentRole.DEVELOPER: WorkerResult,
    AgentRole.REVIEWER: ReviewResult,
    AgentRole.REPAIR: WorkerResult,
}


def role_definition(role: AgentRole) -> RoleDefinition:
    responsibility, capabilities = _RESPONSIBILITIES[role]
    output_contract, authority_boundaries = _ROLE_CONTRACTS[role]
    writable = role in {AgentRole.DEVELOPER, AgentRole.TESTER, AgentRole.DOCUMENTATION}
    return RoleDefinition(
        role=role,
        responsibility=responsibility,
        capabilities=capabilities,
        authority_boundaries=authority_boundaries,
        output_contract=output_contract,
        permissions=PermissionProfile(
            allowed_tools=_WRITE
            if writable
            else (*_READ, ToolName.TEST_RUN)
            if role == AgentRole.REVIEWER
            else _READ
        ),
        can_approve_acceptance=role == AgentRole.REVIEWER,
    )


def provider_output_schema(role: AgentRole) -> dict[str, JsonValue]:
    """Return the validated output shape for a provider-backed role.

    Service-backed roles produce persisted evidence through their application
    services and cannot be dispatched as free-form provider workers.
    """
    model = _PROVIDER_OUTPUT_MODELS.get(role)
    if model is None:
        raise PolicyDeniedError("This role is backed by a deterministic service")
    return cast(dict[str, JsonValue], model.model_json_schema())


def effective_tools(role: AgentRole, project: PermissionProfile) -> tuple[ToolName, ...]:
    return tuple(
        tool
        for tool in role_definition(role).permissions.allowed_tools
        if tool in project.allowed_tools
    )
