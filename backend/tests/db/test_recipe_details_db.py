"""Role 5 recipe endpoints and household stars against the real seeded database."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import clock, mock
from app.auth import DEV_CLAIMS, CurrentUser
from app.db import models as m
from app.db.session import transaction
from app.errors import ApiError, ErrorCode
from app.main import app
from app.schemas.recipes import Recipe, StarResult
from app.services import cook
from app.services.identity import get_or_create_user
from app.services.recommendation_inputs import SqlRecommendationInputs
from seed.seed import seed

client = TestClient(app)


@pytest.fixture
def catalogue():
    seed()
    with transaction() as session:
        user = get_or_create_user(session, UUID(DEV_CLAIMS["sub"]), DEV_CLAIMS["email"])
        recipes = SqlRecommendationInputs(session).catalogue(user.household_id).recipes
    return user, recipes


def events(user, recipe_id):
    with transaction() as session:
        rows = list(
            session.scalars(
                select(m.RecipeFeedback)
                .where(
                    m.RecipeFeedback.household_id == user.household_id,
                    m.RecipeFeedback.recipe_id == recipe_id,
                )
                .order_by(m.RecipeFeedback.created_at, m.RecipeFeedback.id)
            )
        )
        session.expunge_all()
        return rows


def test_every_reviewed_recipe_is_available_over_http_with_authoritative_ingredients(catalogue):
    _, recipes = catalogue
    assert len(recipes) == 48
    for candidate in recipes:
        response = client.get(f"/api/recipes/{candidate.id}")
        assert response.status_code == 200, response.text
        actual = Recipe.model_validate(response.json())
        assert actual == Recipe.model_validate(candidate.model_dump())


def test_http_star_unstar_persists_and_repeated_requests_are_no_ops(catalogue):
    user, recipes = catalogue
    recipe_id = recipes[0].id
    for value, expected_events in [(False, 0), (True, 1), (True, 1), (False, 2), (False, 2)]:
        response = client.put(f"/api/recipes/{recipe_id}/star", json={"starred": value})
        assert response.status_code == 200, response.text
        assert StarResult.model_validate(response.json()).starred == value
        assert client.get(f"/api/recipes/{recipe_id}").json()["starred"] == value
        assert len(events(user, recipe_id)) == expected_events
        with transaction() as session:
            candidate = next(
                r
                for r in SqlRecommendationInputs(session).catalogue(user.household_id).recipes
                if r.id == recipe_id
            )
            assert candidate.starred == value
    for event in events(user, recipe_id):
        assert event.user_id == user.user_id
        assert event.session_id is None and event.cook_record_id is None


@pytest.mark.parametrize("kind", ["unknown", "unreviewed", "legacy_mock"])
def test_unknown_and_unreviewed_recipes_cannot_be_read_or_starred(catalogue, kind):
    user, recipes = catalogue
    recipe_id = uuid4() if kind == "unknown" else recipes[0].id
    if kind == "unreviewed":
        with transaction() as session:
            session.get(m.Recipe, recipe_id).reviewed = False
    elif kind == "legacy_mock":
        recipe_id = mock.mock_id("recipe/tomato-egg")
    for response in [
        client.get(f"/api/recipes/{recipe_id}"),
        client.put(f"/api/recipes/{recipe_id}/star", json={"starred": True}),
    ]:
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
    assert not events(user, recipe_id)


def test_households_have_independent_stars_and_members_share_their_household_state(catalogue):
    user, recipes = catalogue
    recipe_id = recipes[0].id
    with transaction() as session:
        other = get_or_create_user(session, uuid4(), "other@example.test")
        member_id = uuid4()
        session.add(m.User(id=member_id, email="member@example.test"))
        session.flush()
        session.add(m.HouseholdMember(household_id=user.household_id, user_id=member_id))
    member = CurrentUser(member_id, user.household_id, "member@example.test")
    cook.set_star(user, recipe_id, True)
    assert cook.get_recipe(member, recipe_id).starred
    assert not cook.get_recipe(other, recipe_id).starred
    cook.set_star(other, recipe_id, True)
    cook.set_star(member, recipe_id, False)
    assert not cook.get_recipe(user, recipe_id).starred
    assert cook.get_recipe(other, recipe_id).starred
    assert events(user, recipe_id)[-1].user_id == member.user_id


def test_star_changes_do_not_write_taste_weights_or_use_rating_events_as_stars(catalogue):
    user, recipes = catalogue
    recipe_id = recipes[0].id
    with transaction() as session:
        session.add(
            m.Preferences(household_id=user.household_id, taste_weights={"cuisine:chinese": 0.5})
        )
    cook.set_star(user, recipe_id, True)
    with transaction() as session:
        session.add(
            m.RecipeFeedback(
                household_id=user.household_id,
                user_id=user.user_id,
                recipe_id=recipe_id,
                signal="skipped",
                created_at=clock.now() + timedelta(days=1),
            )
        )
    assert cook.get_recipe(user, recipe_id).starred
    cook.set_star(user, recipe_id, False)
    with transaction() as session:
        assert session.get(m.Preferences, user.household_id).taste_weights == {
            "cuisine:chinese": 0.5
        }


def test_later_star_actions_win_even_when_clock_is_behind_prior_event(catalogue, monkeypatch):
    user, recipes = catalogue
    recipe_id = recipes[0].id
    future = clock.now() + timedelta(days=1)
    with transaction() as session:
        session.add(
            m.RecipeFeedback(
                household_id=user.household_id,
                user_id=user.user_id,
                recipe_id=recipe_id,
                signal="starred",
                created_at=future,
            )
        )
    monkeypatch.setattr(clock, "now", lambda: future - timedelta(days=2))
    cook.set_star(user, recipe_id, False)
    cook.set_star(user, recipe_id, True)
    stored = events(user, recipe_id)
    assert [row.signal for row in stored] == ["starred", "unstarred", "starred"]
    assert stored[0].created_at < stored[1].created_at < stored[2].created_at
    assert cook.get_recipe(user, recipe_id).starred


@pytest.mark.parametrize("values", [(True, True), (True, False)])
def test_concurrent_star_requests_have_one_serial_order(catalogue, values):
    user, recipes = catalogue
    recipe_id = recipes[0].id
    barrier = Barrier(2)

    def change(value):
        barrier.wait(timeout=10)
        return cook.set_star(user, recipe_id, value)

    with ThreadPoolExecutor(max_workers=2) as workers:
        pending = [workers.submit(change, value) for value in values]
        for future, value in zip(pending, values, strict=True):
            assert future.result(timeout=15).starred == value
    stored = events(user, recipe_id)
    if values == (True, True):
        assert [event.signal for event in stored] == ["starred"]
    else:
        assert [event.signal for event in stored] in [["starred"], ["starred", "unstarred"]]
    assert all(a.created_at < b.created_at for a, b in zip(stored, stored[1:], strict=False))
    assert cook.get_recipe(user, recipe_id).starred == (stored[-1].signal == "starred")


def test_failure_before_commit_rolls_back_star_event(catalogue, monkeypatch):
    user, recipes = catalogue
    recipe_id = recipes[0].id

    @contextmanager
    def fail_at_commit():
        with transaction() as session:
            yield session
            session.flush()
            raise RuntimeError("Injected failure after write")

    monkeypatch.setattr(cook, "transaction", fail_at_commit)
    with pytest.raises(RuntimeError, match="Injected failure"):
        cook.set_star(user, recipe_id, True)
    assert not events(user, recipe_id)


def test_missing_household_cannot_create_star_events(catalogue):
    user, recipes = catalogue
    invalid = CurrentUser(user.user_id, uuid4(), user.email)
    with pytest.raises(ApiError) as error:
        cook.set_star(invalid, recipes[0].id, True)
    assert error.value.code == ErrorCode.NOT_FOUND
    assert not events(user, recipes[0].id)
