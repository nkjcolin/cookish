"""Profile and household preferences. Role 2 owns this file.

A user is only a login. The household owns the kitchen, the preferences and every stock
change, so everything below finds the household first.
"""

import re
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.db import models as m
from app.db.session import transaction
from app.errors import ApiError, ErrorCode
from app.schemas.identity import Household, Me, Preferences, PreferencesUpdate, User


def get_me(user: CurrentUser) -> Me:
    """The caller, their household, and their preferences (None until onboarding is done)."""
    with transaction() as s:
        row = s.get(m.User, user.user_id)
        household = s.get(m.Household, user.household_id)
        if row is None or household is None:
            raise ApiError(ErrorCode.NOT_FOUND, "User not found")
        prefs = s.get(m.Preferences, user.household_id)
        return Me(
            user=User.model_validate(row),
            household=Household.model_validate(household),
            preferences=None if prefs is None else Preferences.model_validate(prefs),
        )


def save_preferences(user: CurrentUser, body: PreferencesUpdate) -> Preferences:
    """Replace the household's preferences with what the user chose in onboarding or settings.

    The first save also starts the remembered Cook and Shop people counts at household_size.
    Later saves leave those counts, and the learned taste weights, alone: Cook and Shop own them.
    """
    with transaction() as s:
        disliked = list(dict.fromkeys(body.disliked_ingredient_ids))
        _require_known_ingredients(s, disliked)
        chosen = {
            "allergens": _values(body.allergens),
            "diets": _values(body.diets),
            "equipment": _values(body.equipment),
            "cuisines": _values(body.cuisines),
            "disliked_ingredient_ids": disliked,
            "max_cook_minutes": body.max_cook_minutes,
            "max_difficulty": body.max_difficulty,
            "household_size": body.household_size,
        }
        statement = insert(m.Preferences).values(
            household_id=user.household_id,
            **chosen,
            last_cook_people=body.household_size,
            last_shop_people=body.household_size,
        )
        s.execute(
            statement.on_conflict_do_update(
                index_elements=["household_id"], set_={**chosen, "updated_at": func.now()}
            )
        )
        saved = s.get(m.Preferences, user.household_id, populate_existing=True)
        return Preferences.model_validate(saved)


def get_or_create_user(s: Session, user_id: UUID, email: str) -> CurrentUser:
    """Called by app/auth.py on every request.

    `user_id` is the Cognito `sub`. The first time a user is seen, create them and a household
    of one, so that any endpoint can be the first one called.
    """
    found = _find_household(s, user_id)
    if found is None:
        # The app loads several screens at once, so a new user's first requests arrive together.
        # Take a lock for this user, then look again: the request that waited finds the
        # household the other one just made instead of creating a second.
        s.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(str(user_id), 0))))
        found = _find_household(s, user_id)
    if found is None:
        found = _create_user_and_household(s, user_id, email)

    household_id, stored_email = found
    if email and email != stored_email:
        s.execute(update(m.User).where(m.User.id == user_id).values(email=email))
    return CurrentUser(user_id=user_id, household_id=household_id, email=email or stored_email)


def get_preferences(s: Session, household_id: UUID) -> Preferences:
    """For Role 5's services. Raises NOT_FOUND before onboarding is completed."""
    row = s.get(m.Preferences, household_id)
    if row is None:
        raise ApiError(ErrorCode.NOT_FOUND, "Preferences have not been saved yet")
    return Preferences.model_validate(row)


def _find_household(s: Session, user_id: UUID) -> tuple[UUID, str] | None:
    """The user's household and stored email. With several households, the one they own first."""
    row = s.execute(
        select(m.HouseholdMember.household_id, m.User.email)
        .join(m.User, m.User.id == m.HouseholdMember.user_id)
        .join(m.Household, m.Household.id == m.HouseholdMember.household_id)
        .where(m.HouseholdMember.user_id == user_id)
        .order_by((m.HouseholdMember.role == "owner").desc(), m.Household.created_at)
        .limit(1)
    ).first()
    return None if row is None else (row.household_id, row.email)


def _create_user_and_household(s: Session, user_id: UUID, email: str) -> tuple[UUID, str]:
    name = _first_name(email)
    s.execute(
        insert(m.User)
        .values(id=user_id, email=email, display_name=name or None)
        .on_conflict_do_nothing(index_elements=["id"])
    )
    household_id = s.execute(
        insert(m.Household)
        .values(name=f"{name}'s kitchen" if name else "My kitchen")
        .returning(m.Household.id)
    ).scalar_one()
    s.execute(
        insert(m.HouseholdMember).values(household_id=household_id, user_id=user_id, role="owner")
    )
    return household_id, email


def _first_name(email: str) -> str:
    """'dev@cookish.test' -> 'Dev'; 'john.doe+x@mail.com' -> 'John'; nothing usable -> ''."""
    match = re.match(r"[A-Za-z]+", email.split("@")[0])
    return match.group().capitalize() if match else ""


def _values(items: list) -> list[str]:
    return list(dict.fromkeys(item.value for item in items))


def _require_known_ingredients(s: Session, ids: list[UUID]) -> None:
    if not ids:
        return
    known = set(s.scalars(select(m.Ingredient.id).where(m.Ingredient.id.in_(ids))))
    unknown = [str(i) for i in ids if i not in known]
    if unknown:
        raise ApiError(
            ErrorCode.VALIDATION,
            "Some disliked ingredients are not in the catalogue",
            {"disliked_ingredient_ids": unknown},
        )
