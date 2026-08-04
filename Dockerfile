# Builder
FROM python:3.12-slim AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic

RUN uv sync --frozen --no-dev


# Runtime
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY src ./src
COPY lib ./lib
COPY alembic.ini ./
COPY alembic ./alembic
COPY docker-entrypoint.sh ./docker-entrypoint.sh

ENV PYTHONPATH=/app/src
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["python", "-m", "story_graph.web"]