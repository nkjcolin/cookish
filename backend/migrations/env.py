"""Alembic's entry point: tells it which database to use and which tables should exist.

The database comes from app/db/session.py (DATABASE_URL locally, the secret on AWS), so
migrations and the app always talk to the same place. The tables come from app/db/models.py.
"""

from logging.config import fileConfig

from alembic import context

from app.db.models import Base
from app.db.session import engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)  # prints migration progress

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Print the SQL instead of running it (`alembic upgrade head --sql`)."""
    context.configure(
        url=engine().url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine().connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
