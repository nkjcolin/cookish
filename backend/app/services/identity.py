"""Profile and household preferences. STUB — Role 2 replaces the function bodies."""

from uuid import UUID

from sqlalchemy.orm import Session

from app import mock
from app.auth import CurrentUser
from app.schemas.identity import Household, Me, Preferences, PreferencesUpdate, User


def get_me(user: CurrentUser) -> Me:
    """Create the user and a one-member household on the first call."""
    return Me(
        user=User(id=user.user_id, email=user.email, display_name="Dev"),
        household=Household(id=user.household_id, name="Dev's kitchen"),
        preferences=mock.preferences(),
    )


def save_preferences(user: CurrentUser, body: PreferencesUpdate) -> Preferences:
    return mock.preferences().model_copy(update=body.model_dump())


def get_or_create_user(s: Session, user_id: UUID, email: str) -> CurrentUser:
    """Called by app/auth.py on every request.

    `user_id` is the Cognito `sub`. The first time a user is seen, create them and a
    household of one, so that any endpoint can be the first one called.
    """
    return CurrentUser(user_id=user_id, household_id=mock.HOUSEHOLD_ID, email=email)


def get_preferences(s: Session, household_id: UUID) -> Preferences:
    """For Role 5's services. Raises NOT_FOUND before onboarding is completed."""
    return mock.preferences()
