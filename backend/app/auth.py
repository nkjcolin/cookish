"""Who is calling.

STUB (Roles 2 and 3): every request is treated as one fixed development user. The real
version reads the Cognito claims that API Gateway has already verified and looks up the
caller's household. `household_id` must always come from here, never from a request body.
"""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app import mock


@dataclass(frozen=True)
class CurrentUser:
    user_id: UUID
    household_id: UUID
    email: str


def get_current_user() -> CurrentUser:
    return CurrentUser(
        user_id=mock.USER_ID, household_id=mock.HOUSEHOLD_ID, email="dev@cookish.test"
    )


User = Annotated[CurrentUser, Depends(get_current_user)]
