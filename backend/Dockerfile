# Development image for `docker compose up`. The Lambda package is built by SAM, not from this.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Keep the virtualenv outside /app so mounting the source over /app does not hide it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen

COPY . .

EXPOSE 8000
CMD ["sh", "-c", "uv run --frozen alembic upgrade head && uv run --frozen python -m seed.seed && uv run --frozen python -m seed.demo && exec uv run --frozen uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]

