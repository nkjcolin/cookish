"""The single error format used by every endpoint (docs/SPEC.md, A7).

A copy of backend/app/errors.py, so that the frontend gets the same shape from both
Lambdas. tests/test_contract.py fails if the two drift apart.

Code raises ApiError; everything else that can go wrong is converted to the
same envelope here, so the frontend only ever handles one shape.
"""

import logging
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    VALIDATION = "VALIDATION"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    STALE_REVISION = "STALE_REVISION"
    CONFLICT = "CONFLICT"
    NO_RESULT = "NO_RESULT"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    INTERNAL = "INTERNAL"


_STATUS_FOR_CODE = {
    ErrorCode.VALIDATION: 422,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.STALE_REVISION: 409,
    ErrorCode.CONFLICT: 409,
    ErrorCode.NO_RESULT: 404,
    ErrorCode.UPSTREAM_UNAVAILABLE: 503,
    ErrorCode.INTERNAL: 500,
}

_CODE_FOR_STATUS = {
    401: ErrorCode.UNAUTHENTICATED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    409: ErrorCode.CONFLICT,
}


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(Exception):
    def __init__(self, code: ErrorCode, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _envelope(
    code: ErrorCode, message: str, details: dict[str, Any] | None = None, status: int | None = None
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details or {}))
    return JSONResponse(
        status_code=status or _STATUS_FOR_CODE[code], content=jsonable_encoder(body)
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _envelope(exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Pydantic's `ctx` can hold exception objects, which are not JSON-serialisable.
        errors = [{k: v for k, v in e.items() if k != "ctx"} for e in exc.errors()]
        return _envelope(ErrorCode.VALIDATION, "Request validation failed", {"errors": errors})

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        fallback = ErrorCode.INTERNAL if exc.status_code >= 500 else ErrorCode.VALIDATION
        code = _CODE_FOR_STATUS.get(exc.status_code, fallback)
        return _envelope(code, str(exc.detail), status=exc.status_code)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _envelope(ErrorCode.INTERNAL, "Internal server error")
