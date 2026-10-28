FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first: this layer is rebuilt only when pyproject.toml or uv.lock change.
# Dev dependencies (Docling, pytest, ruff) are left out; ingestion runs from a laptop, not here.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# alembic stays in the image so migrations can run from it: `alembic upgrade head`.
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

RUN useradd --create-home appuser
USER appuser

ENV PATH="/app/.venv/bin:$PATH"

# Hosts like Render inject PORT; 8000 is the local default. 0.0.0.0 so the port is reachable
# from outside the container.
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", 8000)}/health')"
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
