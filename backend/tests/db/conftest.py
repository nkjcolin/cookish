"""Fixtures for the tests in this folder, which need a real Postgres. Role 2 owns these.

The throwaway database itself comes from tests/conftest.py. Here, every test starts from and
leaves behind empty tables.
"""

import pytest
from sqlalchemy import text

from app.db import session as db_session
from app.db.models import Base


def _empty_all_tables() -> None:
    names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    with db_session.engine().begin() as connection:
        connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def empty_tables(database):
    if database is None:
        pytest.skip("No Postgres. Start it: docker compose up -d db")
    _empty_all_tables()
    yield
    _empty_all_tables()
