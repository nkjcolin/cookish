"""The identity service against a real Postgres."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.auth import DEV_CLAIMS, CurrentUser
from app.db import models as m
from app.db.session import transaction
from app.errors import ApiError, ErrorCode
from app.schemas.identity import PreferencesUpdate
from app.services import identity

USER = UUID("11111111-1111-4111-8111-111111111111")
OTHER = UUID("22222222-2222-4222-8222-222222222222")


def _login(user_id: UUID = USER, email: str = "dev@cookish.test") -> CurrentUser:
    with transaction() as s:
        return identity.get_or_create_user(s, user_id, email)


def _count(model) -> int:
    with transaction() as s:
        return s.scalar(select(func.count()).select_from(model))


def test_first_login_creates_user_household_and_membership():
    user = _login()
    assert (_count(m.User), _count(m.Household), _count(m.HouseholdMember)) == (1, 1, 1)
    with transaction() as s:
        member = s.scalars(select(m.HouseholdMember)).one()
        assert member.role == "owner" and member.household_id == user.household_id
        assert s.get(m.Household, user.household_id).name == "Dev's kitchen"
        assert s.get(m.User, USER).display_name == "Dev"


def test_later_logins_find_the_same_household():
    first = _login()
    second = _login()
    assert first == second
    assert (_count(m.User), _count(m.Household)) == (1, 1)


def test_a_changed_email_is_kept_and_the_household_is_unchanged():
    first = _login(email="dev@cookish.test")
    second = _login(email="new@cookish.test")
    assert second.household_id == first.household_id and second.email == "new@cookish.test"
    with transaction() as s:
        assert s.get(m.User, USER).email == "new@cookish.test"


def test_different_users_get_different_households():
    assert _login(USER).household_id != _login(OTHER, "other@cookish.test").household_id


def test_simultaneous_first_requests_create_exactly_one_household():
    workers = 5
    start = Barrier(workers)

    def first_request(_):
        start.wait()  # all five arrive together, as the app's first screens do
        return _login().household_id

    with ThreadPoolExecutor(workers) as pool:
        households = list(pool.map(first_request, range(workers)))
    assert len(set(households)) == 1
    assert (_count(m.Household), _count(m.HouseholdMember)) == (1, 1)


def test_get_me_is_empty_until_onboarding_is_saved():
    user = _login()
    me = identity.get_me(user)
    assert me.user.email == "dev@cookish.test" and me.household.name == "Dev's kitchen"
    assert me.preferences is None
    identity.save_preferences(user, PreferencesUpdate(allergens=["peanut"]))
    assert identity.get_me(user).preferences.allergens == ["peanut"]


def test_first_save_starts_the_remembered_people_counts_at_household_size():
    user = _login()
    saved = identity.save_preferences(user, PreferencesUpdate(household_size=4))
    assert (saved.household_size, saved.last_cook_people, saved.last_shop_people) == (4, 4, 4)
    assert saved.last_shop_meals == 3


def test_saving_again_replaces_choices_but_not_what_cook_and_shop_own():
    user = _login()
    identity.save_preferences(user, PreferencesUpdate(allergens=["egg"], cuisines=["malay"]))
    with transaction() as s:  # Cook and Shop update these as people use the app
        row = s.get(m.Preferences, user.household_id)
        row.last_shop_meals = 5
        row.taste_weights = {"tag:low_oil": 0.5}
    saved = identity.save_preferences(
        user, PreferencesUpdate(allergens=["soy"], cuisines=[], household_size=3)
    )
    assert saved.allergens == ["soy"] and saved.cuisines == [] and saved.household_size == 3
    assert saved.last_shop_meals == 5
    with transaction() as s:
        assert s.get(m.Preferences, user.household_id).taste_weights == {"tag:low_oil": 0.5}


def test_repeated_choices_are_stored_once():
    user = _login()
    saved = identity.save_preferences(user, PreferencesUpdate(diets=["vegan", "vegan"]))
    assert saved.diets == ["vegan"]


def test_an_unknown_disliked_ingredient_is_rejected_and_nothing_is_saved():
    user = _login()
    with pytest.raises(ApiError) as error:
        identity.save_preferences(user, PreferencesUpdate(disliked_ingredient_ids=[uuid4()]))
    assert error.value.code == ErrorCode.VALIDATION
    assert _count(m.Preferences) == 0


def test_a_known_disliked_ingredient_is_accepted():
    user = _login()
    ingredient = uuid4()
    with transaction() as s:
        s.add(
            m.Ingredient(
                id=ingredient,
                canonical_name="test herb",
                category="produce",
                default_storage="fridge",
            )
        )
    saved = identity.save_preferences(user, PreferencesUpdate(disliked_ingredient_ids=[ingredient]))
    assert saved.disliked_ingredient_ids == [ingredient]


def test_get_preferences_is_not_found_until_onboarding_is_saved():
    user = _login()
    with transaction() as s, pytest.raises(ApiError) as error:
        identity.get_preferences(s, user.household_id)
    assert error.value.code == ErrorCode.NOT_FOUND
    identity.save_preferences(user, PreferencesUpdate(household_size=2))
    with transaction() as s:
        assert identity.get_preferences(s, user.household_id).household_size == 2


def test_preferences_are_private_to_a_household():
    mine, theirs = _login(USER), _login(OTHER, "other@cookish.test")
    identity.save_preferences(mine, PreferencesUpdate(allergens=["peanut"]))
    assert identity.get_me(theirs).preferences is None
    with transaction() as s, pytest.raises(ApiError):
        identity.get_preferences(s, theirs.household_id)


def test_the_demo_household_is_found_not_duplicated():
    from seed.demo import DEMO_HOUSEHOLD_ID, seed_demo
    from seed.seed import seed

    seed()
    seed_demo()
    user = _login(UUID(DEV_CLAIMS["sub"]), DEV_CLAIMS["email"])
    assert user.household_id == DEMO_HOUSEHOLD_ID
    assert _count(m.Household) == 1
    me = identity.get_me(user)
    assert me.household.name == "Dev's kitchen" and me.preferences is not None
