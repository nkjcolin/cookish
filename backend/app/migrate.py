"""AWS: bring the database up to date. Role 2 owns this file.

Run it as a Lambda (`app.migrate.handler`) inside the same network as the database, once per
deploy. It does the same two things the Dockerfile's start command does locally, except for
the demo household, which must never exist on AWS:

1. `alembic upgrade head`: create or change the tables.
2. `seed.seed`: load the ingredient catalogue and the recipes.

Both are safe to run again, so a retried deploy does no harm. A database lock makes two runs at
the same time take turns, so a double click cannot make both change tables together.

Locally you can try it with:  uv run python -m app.migrate
"""

import json
import sys
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text

from app.db.session import engine

BACKEND = Path(__file__).resolve().parents[1]

# Any number will do, as long as nothing else uses it: it names the lock.
LOCK_KEY = 726_001


def run_migrations() -> str | None:
    """Bring the tables up to the newest migration. Returns the revision now in place."""
    config = Config()  # no ini file, so Alembic leaves the logging alone
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(config, "head")
    with engine().connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def run_seed() -> dict[str, int]:
    """Load ingredients and recipes. A file with a mistake stops everything, writing nothing."""
    from seed.seed import SeedError, seed

    try:
        return seed()
    except SeedError as error:
        raise RuntimeError(
            "Seeding stopped, nothing was written: " + "; ".join(error.problems)
        ) from error


def handler(event: Any = None, context: Any = None) -> dict[str, Any]:
    """The Lambda entry point. The event is ignored."""
    request_id = getattr(context, "aws_request_id", None)
    # A session-level lock lives on this connection, so it is held while the work uses others.
    with engine().connect() as lock:
        lock.execute(text("SELECT pg_advisory_lock(:key)"), {"key": LOCK_KEY})
        try:
            revision = run_migrations()
            counts = run_seed()
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
    result = {"revision": revision, "seed": counts}
    print(json.dumps({"message": "database ready", "request_id": request_id, **result}))
    return result


if __name__ == "__main__":
    json.dump(handler(), sys.stdout, indent=2)
    print()
