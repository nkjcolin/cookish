"""The database connection (docs/init.md, "Database transactions"). Role 2 owns this file.

Services open one transaction per request and pass the session on:

    with transaction() as s:
        record = ...                                  # Role 5's own tables
        change = apply_stock_event(s, user, ...)      # Role 2's inventory
    # committed here; rolled back if anything above raised

Nothing connects until the first query, so code that never queries needs no database.

Where the database is, in order of priority (`database_url`):
1. DATABASE_URL, a full URL. docker-compose and the tests set this.
2. DB_SECRET_ARN, the name of a Secrets Manager secret holding the login. This is AWS.
3. The local docker-compose database.
"""

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

# docker-compose.yml sets DATABASE_URL; this default is the same database seen from the host.
LOCAL_URL = "postgresql+psycopg://cookish:cookish@localhost:5432/cookish"

# What the secret must contain. These are the field names RDS itself uses in the secrets it
# creates, so a secret made by RDS or by the standard CloudFormation template already fits.
SECRET_REQUIRED = ("username", "password", "host")


def _read_secret(arn: str) -> dict[str, Any]:
    """The secret's JSON. boto3 comes with the Lambda Python runtime, so it is imported only
    here and nothing else needs it."""
    import boto3

    reply = boto3.client("secretsmanager").get_secret_value(SecretId=arn)
    return json.loads(reply["SecretString"])


def url_from_secret(secret: dict[str, Any]) -> URL:
    """Build the connection URL from a secret. Passwords may contain any character.

    The error names the missing fields but never prints a value from the secret.
    """
    missing = [key for key in SECRET_REQUIRED if not secret.get(key)]
    if missing:
        raise RuntimeError(f"The database secret has no value for: {', '.join(missing)}")
    return URL.create(
        "postgresql+psycopg",
        username=secret["username"],
        password=secret["password"],
        host=secret["host"],
        port=int(secret.get("port") or 5432),
        database=secret.get("dbname") or os.environ.get("DB_NAME", "cookish"),
        # RDS for PostgreSQL 15 and later only accepts encrypted connections.
        query={"sslmode": os.environ.get("DB_SSLMODE", "require")},
    )


def database_url() -> str | URL:
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return explicit
    secret_arn = os.environ.get("DB_SECRET_ARN")
    if secret_arn:
        return url_from_secret(_read_secret(secret_arn))
    return LOCAL_URL


@cache
def engine() -> Engine:
    # Created once per process, so a warm Lambda reuses its connection (and reads the secret
    # once). A Lambda instance handles one request at a time and needs one connection; the
    # overflow is for local servers, which run requests in parallel threads.
    return create_engine(
        database_url(),
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
