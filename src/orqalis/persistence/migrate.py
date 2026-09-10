from importlib.resources import files

from alembic import command
from alembic.config import Config


def upgrade_database() -> None:
    """Apply packaged historical migrations, independent of the working directory."""
    config = Config()
    config.set_main_option(
        "script_location",
        str(files("orqalis").joinpath("persistence/migrations")).replace("%", "%%"),
    )
    command.upgrade(config, "head")
