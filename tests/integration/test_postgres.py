from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect
from sqlalchemy.orm import Session

from orqalis.domain.errors import ConflictError
from orqalis.domain.project import Project
from orqalis.persistence.projects import SQLProjectRepository
from orqalis.persistence.schema import Base

pytestmark = pytest.mark.postgres


def test_migration_roundtrip_and_schema(database: Engine) -> None:
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    with database.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    command.downgrade(config, "base")
    assert "projects" not in inspect(database).get_table_names()
    command.upgrade(config, "head")
    assert "projects" in inspect(database).get_table_names()


def test_project_roundtrip_uniqueness_and_rollback(database: Engine, tmp_path: Path) -> None:
    project = Project(name="fixture", repo_root=tmp_path / str(uuid4()), default_branch="main")
    with Session(database) as session, session.begin():
        SQLProjectRepository(session).add(project)
    with Session(database) as session:
        repo = SQLProjectRepository(session)
        assert repo.get(project.id) == project
        assert repo.get_by_root(project.repo_root) == project
        with pytest.raises(ConflictError):
            repo.add(Project(name="duplicate", repo_root=project.repo_root, default_branch="main"))
        session.rollback()
        assert repo.get(project.id) == project
    rolled_back = Project(name="rollback", repo_root=tmp_path / str(uuid4()), default_branch="main")
    with Session(database) as session:
        SQLProjectRepository(session).add(rolled_back)
        session.rollback()
    with Session(database) as session:
        assert SQLProjectRepository(session).get(rolled_back.id) is None


def test_project_init_idempotency_and_cli(database: Engine, git_repo: Path) -> None:
    import json

    from typer.testing import CliRunner

    from orqalis.cli.app import app
    from orqalis.core.projects import ProjectService
    from orqalis.git.service import LocalGitService
    from orqalis.persistence.database import session_factory
    from orqalis.persistence.unit_of_work import SQLProjectUnitOfWork

    service = ProjectService(
        lambda: SQLProjectUnitOfWork(session_factory(database)), LocalGitService()
    )
    project = service.initialize(git_repo)
    assert service.initialize(git_repo / "tests") == project
    assert project.settings.repository_profile.languages == ("Python",)
    runner = CliRunner()
    result = runner.invoke(app, ["init", "--repo", str(git_repo), "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["id"] == str(project.id)
    result = runner.invoke(app, ["status", "--repo", str(git_repo), "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["git"]["branch"] == "main"


def test_installed_migrations_do_not_need_checkout_config(
    database: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from orqalis.cli.app import app

    monkeypatch.setenv("ORQALIS_DATABASE_URL", database.url.render_as_string(hide_password=False))
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["migrate"])
    assert result.exit_code == 0, result.output
    assert "Database upgraded" in result.output
