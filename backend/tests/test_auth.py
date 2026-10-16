from datetime import UTC, datetime
from uuid import uuid4

import pytest
from starlette.requests import Request

from app import clock, mock
from app.auth import get_current_user
from app.errors import ApiError, ErrorCode


def _request(event: dict | None = None) -> Request:
    scope = {"type": "http", "method": "GET", "path": "/api/me", "headers": []}
    if event is not None:
        scope["aws.event"] = event
    return Request(scope)


def _lambda_event(claims: dict | None) -> dict:
    authorizer = {"jwt": {"claims": claims}} if claims is not None else {}
    return {"requestContext": {"authorizer": authorizer}}


def test_local_requests_are_the_development_user() -> None:
    user = get_current_user(_request())

    assert user.user_id == mock.USER_ID


def test_lambda_requests_use_the_verified_claims() -> None:
    sub = uuid4()

    user = get_current_user(_request(_lambda_event({"sub": str(sub), "email": "a@b.test"})))

    assert user.user_id == sub
    assert user.email == "a@b.test"


def test_lambda_request_without_claims_is_rejected() -> None:
    with pytest.raises(ApiError) as raised:
        get_current_user(_request(_lambda_event(None)))

    assert raised.value.code == ErrorCode.UNAUTHENTICATED


def test_today_is_the_singapore_date(monkeypatch: pytest.MonkeyPatch) -> None:
    # 20:00 UTC on 1 March is 04:00 on 2 March in Singapore.
    utc = datetime(2026, 3, 1, 20, 0, tzinfo=UTC)
    monkeypatch.setattr(clock, "now", lambda: utc.astimezone(clock.SINGAPORE))

    assert clock.today().isoformat() == "2026-03-02"
