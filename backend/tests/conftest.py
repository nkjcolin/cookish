"""Shared test setup. Role 2 owns this file.

Tests never touch the development database. At the start of a run a throwaway database is
created on the same Postgres server, built with the real Alembic migrations, and dropped at the
end. DATABASE_URL points at it for the whole run, so running the tests cannot change your demo
kitchen (the contract tests save preferences, for example).

Postgres is found at DATABASE_URL, or at the docker-compose one (`docker compose up -d db`).
Without it, tests that need no database still run; those in tests/db are skipped and the
contract tests fail. Set REQUIRE_DB=1, as CI does, to stop the whole run instead.
"""

import os
import uuid
import warnings
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from app.db import session as db_session

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def database():
    """The throwaway database's name, or None when no Postgres can be reached."""
    base = make_url(os.environ.get("DATABASE_URL", db_session.LOCAL_URL))
    name = f"cookish_test_{uuid.uuid4().hex[:8]}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
    except OperationalError:
        admin.dispose()
        reason = f"No Postgres at {base.host}:{base.port}. Start it: docker compose up -d db"
        if os.environ.get("REQUIRE_DB"):
            pytest.exit(reason, returncode=1)
        warnings.warn(f"{reason} (tests needing a database will be skipped or fail)", stacklevel=2)
        yield None
        return

    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = base.set(database=name).render_as_string(hide_password=False)
    db_session.engine.cache_clear()  # the engine is cached; make it point at the new database
    config = Config()  # no ini file: env.py then leaves logging alone
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    try:
        command.upgrade(config, "head")
        yield name
    finally:
        db_session.engine().dispose()
        db_session.engine.cache_clear()
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()
