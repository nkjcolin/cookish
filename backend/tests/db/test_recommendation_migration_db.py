"""Recommendation storage upgrades preserve pre-existing user and workflow data."""

from datetime import timedelta
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from app import clock, migrate
from app.db import models as m
from app.db.session import transaction
from app.services.identity import get_or_create_user
from seed.seed import seed


def test_upgrade_preserves_legacy_rows_and_weights_without_inventing_snapshots():
    seed()
    session_id, record_id, basket_id = uuid4(), uuid4(), uuid4()
    weights = {"tag:low_oil": 1.25, "cuisine:chinese": -0.5}
    with transaction() as session:
        user = get_or_create_user(session, uuid4(), "migration@cookish.test")
        recipe_id = session.scalar(select(m.Recipe.id).order_by(m.Recipe.id))
        session.add(m.Preferences(household_id=user.household_id, taste_weights=weights))
        session.add(
            m.PlanSession(
                id=session_id,
                household_id=user.household_id,
                user_id=user.user_id,
                mode="cook",
                people=3,
                constraints={"tags": ["less_oil"]},
                shown_recipe_ids=[recipe_id],
                expires_at=clock.now() + timedelta(hours=12),
            )
        )
        session.flush()
        session.add(
            m.CookRecord(
                id=record_id,
                session_id=session_id,
                household_id=user.household_id,
                user_id=user.user_id,
                recipe_id=recipe_id,
                people=3,
            )
        )
        session.add(
            m.Basket(
                id=basket_id,
                session_id=session_id,
                household_id=user.household_id,
                people=3,
                meals=2,
            )
        )

    config = Config()
    config.set_main_option("script_location", str(migrate.BACKEND / "migrations"))
    # Exercise the upgrade against real rows in the previous schema, not only
    # an empty database. The fixture owns a disposable database for this run.
    try:
        command.downgrade(config, "d0ae2870ce7e")
        command.upgrade(config, "head")
        with transaction() as session:
            old_session = session.get(m.PlanSession, session_id)
            old_record = session.get(m.CookRecord, record_id)
            old_basket = session.get(m.Basket, basket_id)
            assert old_session.people == old_record.people == old_basket.people == 3
            assert old_session.constraints == {"tags": ["less_oil"]}
            assert old_session.shown_recipe_ids == [recipe_id]
            assert old_record.recipe_id == recipe_id
            assert old_basket.meals == 2
            assert old_session.recommendation_state is None
            assert old_record.selection_snapshot is None
            assert old_record.confirmation_snapshot is None
            assert old_basket.planning_snapshot is None
            assert session.get(m.Preferences, user.household_id).taste_weights == weights
            assert session.get(m.RecommendationLearning, user.household_id) is None
            assert list(session.scalars(select(m.RecommendationConfirmation))) == []
    finally:
        # Restore head even if an assertion fails, so later tests and cleanup
        # still see the schema declared by Base.metadata.
        command.upgrade(config, "head")
