"""Database-independent, read-only capability and safe configuration commands."""

import json
from pathlib import Path

import typer

from orqalis.agents.roles import role_definition
from orqalis.cli.dependencies import command_errors
from orqalis.config.settings import Settings
from orqalis.domain.agent import AgentRole
from orqalis.domain.capabilities import SkillMetadata
from orqalis.domain.errors import PolicyDeniedError
from orqalis.security.redaction import safe_diagnostic
from orqalis.skills.registry import SkillRegistry

config_app = typer.Typer(no_args_is_help=True, help="Inspect safe local configuration.")


def discover_skills(settings: Settings) -> tuple[SkillMetadata, ...]:
    registry = SkillRegistry(
        (Path(__file__).parents[1] / "skills" / "bundled", *settings.skill_roots)
    )
    skills = registry.discover()
    if any(safe_diagnostic(skill.model_dump_json()) != skill.model_dump_json() for skill in skills):
        raise PolicyDeniedError("Skill metadata contains private or sensitive content")
    return skills


def agents(json_output: bool = typer.Option(False, "--json")) -> None:
    """List specialized roles and their permission profiles; these are not runtime sessions."""
    roles = tuple(role_definition(role) for role in AgentRole)
    if json_output:
        typer.echo(json.dumps([role.model_dump(mode="json") for role in roles], sort_keys=True))
    else:
        for role in roles:
            typer.echo(f"{role.role}: {role.responsibility}")


def skills(json_output: bool = typer.Option(False, "--json")) -> None:
    """List discoverable skill metadata without loading instruction bodies."""
    with command_errors():
        catalog = discover_skills(Settings())
        if json_output:
            typer.echo(json.dumps([skill.model_dump(mode="json") for skill in catalog]))
        else:
            for skill in catalog:
                typer.echo(f"{skill.id}@{skill.version}: {skill.description}")


@config_app.command("show")
def show_config(json_output: bool = typer.Option(False, "--json")) -> None:
    """Show local options and credential presence; never reveal credentials or the database URL."""
    settings = Settings()
    # Explicit allowlist: future secret settings must never become visible implicitly.
    values: dict[str, object] = {
        "host": safe_diagnostic(settings.host),
        "port": settings.port,
        "log_level": settings.log_level,
        "telemetry_console": settings.telemetry_console,
        "max_repair_iterations": settings.max_repair_iterations,
        "skill_roots": [safe_diagnostic(str(path)) for path in settings.skill_roots],
        "database_url_configured": bool(settings.database_url.get_secret_value()),
        "openai_model": safe_diagnostic(settings.openai_model) if settings.openai_model else None,
        "openai_api_key_configured": bool(settings.openai_api_key),
        "anthropic_model": safe_diagnostic(settings.anthropic_model)
        if settings.anthropic_model
        else None,
        "anthropic_api_key_configured": bool(settings.anthropic_api_key),
    }
    if json_output:
        typer.echo(json.dumps(values, sort_keys=True))
    else:
        for key, value in values.items():
            typer.echo(f"{key}: {value}")
