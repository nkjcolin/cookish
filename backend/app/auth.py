"""Who is calling (docs/init.md, "Who is calling").

On AWS, API Gateway has already verified the Cognito ID token before the request reaches
the Lambda, and passes its claims along in the event. Locally there is no API Gateway, so
every request is treated as one fixed development user. Both go through the same
`identity.get_or_create_user`, which Role 2 implements.

`household_id` must always come from here, never from a request body.
"""

from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Request

from app import mock
from app.db.session import transaction
from app.errors import ApiError, ErrorCode


@dataclass(frozen=True)
class CurrentUser:
    user_id: UUID
    household_id: UUID
    email: str


DEV_CLAIMS = {"sub": str(mock.USER_ID), "email": "dev@cookish.test"}


def _claims(request: Request) -> dict[str, Any]:
    event = request.scope.get("aws.event")  # set by Mangum on Lambda only
    if event is None:
        return DEV_CLAIMS
    claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims")
    if not claims or "sub" not in claims:
        raise ApiError(ErrorCode.UNAUTHENTICATED, "Sign in to continue")
    return claims


def get_current_user(request: Request) -> CurrentUser:
    # Imported here because the identity service itself uses CurrentUser.
    from app.services import identity

    claims = _claims(request)
    with transaction() as s:
        return identity.get_or_create_user(s, UUID(claims["sub"]), claims.get("email", ""))


User = Annotated[CurrentUser, Depends(get_current_user)]
