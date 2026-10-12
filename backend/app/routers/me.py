from fastapi import APIRouter

from app.auth import User
from app.schemas.identity import Me, Preferences, PreferencesUpdate
from app.services import identity

router = APIRouter(tags=["identity"])


@router.get("/me")
def get_me(user: User) -> Me:
    return identity.get_me(user)


@router.put("/household/preferences")
def save_preferences(user: User, body: PreferencesUpdate) -> Preferences:
    return identity.save_preferences(user, body)
