import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.errors import ApiError, ErrorCode
from app.main import create_app


class _Body(BaseModel):
    count: int


@pytest.fixture
def client() -> TestClient:
    app = create_app()

    @app.post("/api/_test/validate")
    def validate(body: _Body) -> _Body:
        return body

    @app.get("/api/_test/stale")
    def stale() -> None:
        raise ApiError(ErrorCode.STALE_REVISION, "Item was changed elsewhere", {"revision": 4})

    @app.get("/api/_test/crash")
    def crash() -> None:
        raise RuntimeError("boom")

    return TestClient(app, raise_server_exceptions=False)


def test_api_error_uses_envelope(client: TestClient) -> None:
    response = client.get("/api/_test/stale")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "STALE_REVISION",
            "message": "Item was changed elsewhere",
            "details": {"revision": 4},
        }
    }


def test_validation_error_uses_envelope(client: TestClient) -> None:
    response = client.post("/api/_test/validate", json={"count": "many"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION"
    assert error["details"]["errors"][0]["loc"] == ["body", "count"]


def test_unknown_route_uses_envelope(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_unexpected_error_hides_details(client: TestClient) -> None:
    response = client.get("/api/_test/crash")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "INTERNAL", "message": "Internal server error", "details": {}}
    }
