from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.errors import ErrorResponse, register_error_handlers
from app.routers import ai, catalogue, cook, health, inventory, me, shop

API_PREFIX = "/api"
AI_PREFIX = "/ai"


def _operation_id(route: APIRoute) -> str:
    # Function names become method names in the generated frontend client.
    return route.name


def create_app() -> FastAPI:
    app = FastAPI(
        title="Cookish API",
        version="0.1.0",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        responses={"4XX": {"model": ErrorResponse}, "5XX": {"model": ErrorResponse}},
        generate_unique_id_function=_operation_id,
    )
    register_error_handlers(app)
    for router in (health, me, catalogue, inventory, cook, shop):
        app.include_router(router.router, prefix=API_PREFIX)
    app.include_router(ai.router, prefix=AI_PREFIX)
    return app


app = create_app()
