from orqalis.domain.agent import AgentRole
from orqalis.domain.capabilities import PermissionProfile, RoleDefinition, ToolName

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


def role_definition(role: AgentRole) -> RoleDefinition:
    responsibility, capabilities = _RESPONSIBILITIES[role]
    writable = role in {AgentRole.DEVELOPER, AgentRole.TESTER, AgentRole.DOCUMENTATION}
    return RoleDefinition(
        role=role,
        responsibility=responsibility,
        capabilities=capabilities,
        permissions=PermissionProfile(
            allowed_tools=_WRITE
            if writable
            else (*_READ, ToolName.TEST_RUN)
            if role == AgentRole.REVIEWER
            else _READ
        ),
        can_approve_acceptance=role == AgentRole.REVIEWER,
    )


def effective_tools(role: AgentRole, project: PermissionProfile) -> tuple[ToolName, ...]:
    return tuple(
        tool
        for tool in role_definition(role).permissions.allowed_tools
        if tool in project.allowed_tools
    )
