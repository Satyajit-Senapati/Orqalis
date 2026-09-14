from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from orqalis.config.settings import Settings
from orqalis.core.projects import ProjectService
from orqalis.domain.errors import OrqalisError
from orqalis.domain.project import Project
from orqalis.git.service import LocalGitService
from orqalis.memory.service import MemoryService
from orqalis.persistence.database import create_database_engine, session_factory
from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork
from orqalis.security.redaction import safe_diagnostic


@contextmanager
def command_errors() -> Iterator[None]:
    """Translate expected local failures without leaking input or connection details."""
    try:
        yield
    except OrqalisError as exc:
        typer.echo(f"{exc.code}: {safe_diagnostic(str(exc))}", err=True)
        raise typer.Exit(1) from None
    except SQLAlchemyError:
        typer.echo("database_error: check PostgreSQL connectivity and migrations", err=True)
        raise typer.Exit(1) from None
    except (ValidationError, ValueError):
        typer.echo("configuration_error: invalid settings or command contract", err=True)
        raise typer.Exit(1) from None
    except OSError:
        typer.echo("filesystem_error: required local path is unavailable", err=True)
        raise typer.Exit(1) from None


@contextmanager
def project_service() -> Iterator[ProjectService]:
    with command_errors():
        engine = create_database_engine(Settings())
        try:
            sessions = session_factory(engine)
            yield ProjectService(lambda: SQLProjectUnitOfWork(sessions), LocalGitService())
        finally:
            engine.dispose()


@contextmanager
def memory_service(path: Path) -> Iterator[tuple[Project, MemoryService]]:
    with project_service() as projects:
        project, _ = projects.status(path)
        yield project, MemoryService(projects.unit_of_work, projects.git)
