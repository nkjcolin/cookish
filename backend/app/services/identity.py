"""Profile and household preferences. STUB — Role 2 replaces the function bodies."""

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
