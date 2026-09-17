from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer
from pydantic import ValidationError

from orqalis.core.projects import ProjectService
from orqalis.domain.errors import OrqalisError
from orqalis.sdk import Orqalis
from orqalis.security.redaction import safe_diagnostic


@contextmanager
def command_errors() -> Iterator[None]:
    """Translate expected local failures without leaking input or connection details."""
    try:
        yield
    except OrqalisError as exc:
        typer.echo(f"{exc.code}: {safe_diagnostic(str(exc))}", err=True)
        raise typer.Exit(1) from None
    except (ValidationError, ValueError):
        typer.echo("configuration_error: invalid settings or command contract", err=True)
        raise typer.Exit(1) from None
    except OSError:
        typer.echo("filesystem_error: required local path is unavailable", err=True)
        raise typer.Exit(1) from None


@contextmanager
def sdk_service(root: Path | None = None) -> Iterator[Orqalis]:
    with command_errors():
        sdk = Orqalis(root=root)
        try:
            yield sdk
        finally:
            sdk.close()


@contextmanager
def project_service(root: Path | None = None) -> Iterator[ProjectService]:
    with sdk_service(root) as sdk:
        yield sdk.projects
