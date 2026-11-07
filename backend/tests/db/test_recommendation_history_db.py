"""Recent meals use completed stock events, never selection or rating timestamps."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app import clock
from app.db import models as m
from app.db.session import transaction
from app.errors import ApiError, ErrorCode
from app.services.identity import get_or_create_user
from app.services.recommendation_sql import RECENT_COOK_WINDOW, SqlRecommendationRepository
from seed.seed import seed


@pytest.fixture
def history():
    seed()
    with transaction() as session:
        user = get_or_create_user(session, uuid4(), "history@example.test")
        stranger = get_or_create_user(session, uuid4(), "elsewhere@example.test")
        recipe_ids = list(session.scalars(select(m.Recipe.id).order_by(m.Recipe.id)))
    return user, stranger, recipe_ids, clock.now()


def record(
    session,
    user,
    recipe_id,
    confirmed_at,
    *,
    selected_at=None,
    status="confirmed",
    event_type="consume",
    event_household=None,
    wrong_target=False,
    undone=False,
):
    selected_at = selected_at or confirmed_at - timedelta(hours=1)
    plan = m.PlanSession(
        id=uuid4(),
        household_id=user.household_id,
        user_id=user.user_id,
        mode="cook",
        people=2,
        created_at=selected_at,
        expires_at=selected_at + timedelta(hours=12),
    )
    session.add(plan)
    session.flush()
    cooked = m.CookRecord(
        id=uuid4(),
        session_id=plan.id,
        recipe_id=recipe_id,
        household_id=user.household_id,
        user_id=user.user_id,
        people=2,
        status=status,
        created_at=selected_at,
    )
    session.add(cooked)
    session.flush()
    event = m.StockEvent(
        id=uuid4(),
        household_id=event_household or user.household_id,
        user_id=user.user_id,
        type=event_type,
        idempotency_key=uuid4(),
        ref_type="cook_session",
        ref_id=uuid4() if wrong_target else cooked.id,
        created_at=confirmed_at,
    )
    session.add(event)
    session.flush()
    cooked.stock_event_id = event.id
    if undone:
        undo = m.StockEvent(
            id=uuid4(),
            household_id=user.household_id,
            user_id=user.user_id,
            type="undo",
            idempotency_key=uuid4(),
            ref_type="cook_session",
            ref_id=cooked.id,
            reverts_event_id=event.id,
            created_at=confirmed_at,
        )
        session.add(undo)
        session.flush()
        event.reverted_by_event_id = undo.id
    session.flush()
    return cooked


def recent(user, as_of):
    with transaction() as session:
        return SqlRecommendationRepository(session, user).recent_recipe_ids(
            user.household_id, as_of=as_of
        )


def test_exact_seven_day_boundary_and_current_time_are_included_but_outside_is_not(history):
    user, _, recipes, now = history
    with transaction() as session:
        for recipe_id, timestamp in zip(
            recipes[:4],
            (
                now - RECENT_COOK_WINDOW,
                now - RECENT_COOK_WINDOW - timedelta(microseconds=1),
                now,
                now + timedelta(microseconds=1),
            ),
            strict=True,
        ):
            record(session, user, recipe_id, timestamp)
    assert recent(user, now) == frozenset({recipes[0], recipes[2]})


def test_confirmation_time_controls_history_not_selection_or_edited_feedback(history):
    user, _, recipes, now = history
    with transaction() as session:
        record(
            session,
            user,
            recipes[0],
            now - timedelta(hours=1),
            selected_at=now - timedelta(days=30),
        )
        old = record(session, user, recipes[1], now - timedelta(days=8))
        # A late rating does not make an eight-day-old meal recent again.
        session.add(
            m.RecipeFeedback(
                household_id=user.household_id,
                user_id=user.user_id,
                recipe_id=old.recipe_id,
                session_id=old.session_id,
                cook_record_id=old.id,
                signal="like",
                created_at=now,
            )
        )
    assert recent(user, now) == frozenset({recipes[0]})


def test_only_completed_unreverted_consumption_for_this_household_counts(history):
    user, stranger, recipes, now = history
    with transaction() as session:
        record(session, user, recipes[0], now)
        record(session, user, recipes[0], now)  # duplicates remain a single recipe penalty
        record(session, user, recipes[1], now, undone=True)
        record(session, user, recipes[2], now, status="selected")
        record(session, user, recipes[3], now, status="abandoned")
        record(session, user, recipes[4], now, event_type="purchase")
        record(session, stranger, recipes[5], now)
        record(session, user, recipes[6], now, event_household=stranger.household_id)
        record(session, user, recipes[7], now, wrong_target=True)
    assert recent(user, now) == frozenset({recipes[0]})
    assert recent(stranger, now) == frozenset({recipes[5]})


def test_history_disappears_after_the_window_and_rejects_foreign_queries_or_naive_time(history):
    user, stranger, recipes, now = history
    with transaction() as session:
        record(session, user, recipes[0], now)
    assert recent(user, now) == frozenset({recipes[0]})
    assert recent(user, now + RECENT_COOK_WINDOW + timedelta(microseconds=1)) == frozenset()
    with transaction() as session:
        repository = SqlRecommendationRepository(session, user)
        with pytest.raises(ApiError) as caught:
            repository.recent_recipe_ids(stranger.household_id, as_of=now)
        assert caught.value.code == ErrorCode.NOT_FOUND
        with pytest.raises(ValueError, match="timezone-aware"):
            repository.recent_recipe_ids(user.household_id, as_of=now.replace(tzinfo=None))
