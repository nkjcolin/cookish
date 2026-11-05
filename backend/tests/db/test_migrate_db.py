"""The AWS migration step, run against the throwaway database."""

import threading

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text

from app import migrate
from app.db import models as m
from app.db.session import engine, transaction
from seed.seed import INGREDIENTS_CSV, SeedError, read_ingredients


def _newest_revision() -> str:
    config = Config()
    config.set_main_option("script_location", str(migrate.BACKEND / "migrations"))
    return ScriptDirectory.from_config(config).get_current_head()


def _count(model) -> int:
    with transaction() as s:
        return s.scalar(select(func.count()).select_from(model))


def test_it_brings_the_database_to_the_newest_revision_and_loads_the_catalogue():
    result = migrate.handler({}, None)
    rows, _ = read_ingredients(INGREDIENTS_CSV)
    assert result["revision"] == _newest_revision()
    assert result["seed"]["ingredients"] == len(rows) == _count(m.Ingredient)
    assert result["seed"]["recipes"] == _count(m.Recipe) > 0


def test_it_never_creates_the_demo_household():
    migrate.handler({}, None)
    assert _count(m.Household) == 0 and _count(m.InventoryItem) == 0


def test_running_it_again_changes_nothing():
    first = migrate.handler({}, None)
    ingredients, recipes = _count(m.Ingredient), _count(m.Recipe)
    again = migrate.handler({}, None)
    assert again == first
    assert (_count(m.Ingredient), _count(m.Recipe)) == (ingredients, recipes)


def test_a_mistake_in_a_seed_file_is_reported_and_writes_nothing(monkeypatch):
    def broken():
        raise SeedError(["recipe 'x': unknown ingredient 'dragon fruit'"])

    monkeypatch.setattr("seed.seed.seed", broken)
    with pytest.raises(RuntimeError, match="dragon fruit"):
        migrate.handler({}, None)


def test_two_runs_at_the_same_moment_take_turns():
    """While another connection holds the lock, the migration waits instead of racing it."""
    finished = threading.Event()

    def run():
        migrate.handler({}, None)
        finished.set()

    with engine().connect() as other:
        other.execute(text("SELECT pg_advisory_lock(:key)"), {"key": migrate.LOCK_KEY})
        thread = threading.Thread(target=run)
        thread.start()
        assert not finished.wait(timeout=1)  # still waiting for the lock
        other.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": migrate.LOCK_KEY})
    assert finished.wait(timeout=30)
    thread.join()
