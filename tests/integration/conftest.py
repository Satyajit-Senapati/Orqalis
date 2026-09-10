import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import Engine

from orqalis.config.settings import Settings
from orqalis.persistence.database import create_database_engine


@pytest.fixture()
def database(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    url = os.environ.get("ORQALIS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set ORQALIS_TEST_DATABASE_URL to a disposable PostgreSQL database")
    monkeypatch.setenv("ORQALIS_DATABASE_URL", url)
    engine = create_database_engine(Settings(database_url=SecretStr(url)))
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    command.upgrade(config, "head")
    try:
        yield engine
    finally:
        engine.dispose()
