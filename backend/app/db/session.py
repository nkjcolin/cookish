"""The database connection (docs/init.md, "Database transactions"). Role 2 owns this file.

Services open one transaction per request and pass the session on:

    with transaction() as s:
        record = ...                                  # Role 5's own tables
        change = apply_stock_event(s, user, ...)      # Role 2's inventory
    # committed here; rolled back if anything above raised

Nothing connects until the first query, so code that never queries needs no database.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

# docker-compose.yml sets DATABASE_URL; this default is the same database seen from the host.
LOCAL_URL = "postgresql+psycopg://cookish:cookish@localhost:5432/cookish"


@cache
def engine() -> Engine:
    # Created once per process, so a warm Lambda reuses its connection. A Lambda instance
    # handles one request at a time and needs one connection; the overflow is for local
    # servers, which run requests in parallel threads.
    # TODO (Roles 2 and 3): on AWS, build the URL from the secret named by DB_SECRET_ARN.
    return create_engine(
        os.environ.get("DATABASE_URL", LOCAL_URL),
        pool_size=1,
        max_overflow=4,
        pool_pre_ping=True,
        pool_recycle=300,
    )


@contextmanager
def transaction() -> Iterator[Session]:
    """One unit of work: commits when the block ends, rolls back if it raises."""
    with Session(engine()) as s, s.begin():
        yield s
