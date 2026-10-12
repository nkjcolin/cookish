from fastapi import FastAPI

from app.errors import ErrorResponse, register_error_handlers
from app.routers import health

API_PREFIX = "/api"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Cookish API",
        version="0.1.0",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        responses={"4XX": {"model": ErrorResponse}, "5XX": {"model": ErrorResponse}},
    )
    register_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    return app


app = create_app()
