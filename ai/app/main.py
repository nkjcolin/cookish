"""The `ai` Lambda: assisted entry under /ai (SPEC A3, B4).

It runs outside the VPC and never touches the database. API Gateway has already checked
the caller's Cognito token before a request reaches it.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI
from fastapi.routing import APIRoute

from app import parse
from app.errors import ErrorResponse, register_error_handlers
from app.model_client import ModelClient, get_client
from app.schemas import (
    DraftResult,
    InterpretRequest,
    InterpretResult,
    ParseImageRequest,
    ParseItemsRequest,
)

AI_PREFIX = "/ai"

# Show the per-call log lines when run locally. On Lambda the runtime has already set up
# logging, and this does nothing.
logging.basicConfig(level=logging.INFO, format="%(message)s")

Client = Annotated[ModelClient, Depends(get_client)]

router = APIRouter(tags=["ai"])


@router.post("/parse-image")
def parse_image(body: ParseImageRequest, client: Client) -> DraftResult:
    return parse.parse_image(body, client)


@router.post("/parse-items")
def parse_items(body: ParseItemsRequest, client: Client) -> DraftResult:
    return parse.parse_items(body, client)


@router.post("/interpret")
def interpret(body: InterpretRequest, client: Client) -> InterpretResult:
    return parse.interpret(body, client)


def _operation_id(route: APIRoute) -> str:
    # Same rule as the backend, so the operation ids match docs/openapi.json.
    return route.name


def create_app() -> FastAPI:
    app = FastAPI(
        title="Cookish AI",
        version="0.1.0",
        openapi_url=f"{AI_PREFIX}/openapi.json",
        docs_url=f"{AI_PREFIX}/docs",
        redoc_url=None,
        responses={"4XX": {"model": ErrorResponse}, "5XX": {"model": ErrorResponse}},
        generate_unique_id_function=_operation_id,
    )
    register_error_handlers(app)
    app.include_router(router, prefix=AI_PREFIX)
    return app


app = create_app()
