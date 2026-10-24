# Development image for Compose/local HTTP testing; Lambda uses Dockerfile.lambda.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Keep the virtualenv outside /app so mounting the source over /app does not hide it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen

# Explicit inputs keep local credentials, receipt photos and experiments out of images.
COPY app ./app
COPY tests ./tests
COPY scripts ./scripts
COPY eval ./eval
COPY README.md .env.example ./

EXPOSE 8000
CMD ["uv", "run", "--frozen", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
