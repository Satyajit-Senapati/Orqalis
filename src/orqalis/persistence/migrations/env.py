from alembic import context

from orqalis.config.settings import Settings
from orqalis.persistence.database import create_database_engine
from orqalis.persistence.schema import Base


def run_migrations() -> None:
    settings = Settings()
    if context.is_offline_mode():
        context.configure(
            url=settings.database_url.get_secret_value(),
            target_metadata=Base.metadata,
            literal_binds=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = create_database_engine(settings)
        try:
            with engine.connect() as connection:
                context.configure(connection=connection, target_metadata=Base.metadata)
                with context.begin_transaction():
                    context.run_migrations()
        finally:
            engine.dispose()


run_migrations()
