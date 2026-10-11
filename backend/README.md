# Backend

FastAPI service for Document Copilot. Run everything below from `backend/`.

## Setup

```bash
uv sync
```

Create `backend/.env` with the variables listed in `app/config.py` (all required except `HOST` and `PORT`). The app fails at startup if any are missing.

## Run

```bash
uv run python app/main.py
```

Or run uvicorn directly:

```bash
uv run uvicorn app.main:app --reload
```

The server listens on `127.0.0.1:8000` by default (override with `HOST` / `PORT`). Check it: `GET /health` → `{"status": "ok"}`. Interactive docs are at `/docs`.

## Migrations

Uses `DATABASE_URL` (direct or session connection, never the transaction pooler; URL-encode special characters in the password).

```bash
uv run alembic upgrade head                      # apply
uv run alembic upgrade head --sql                # print SQL without connecting
uv run alembic revision --autogenerate -m "msg"  # new migration after model changes; review it
uv run alembic downgrade -1                      # roll back one
```

## Test and lint

```bash
uv run pytest -m "not integration"
uv run ruff check app
uv run ruff format app
```

## Dependencies

```bash
uv add <package>          # runtime
uv add --dev <package>    # dev only
```

See [../CLAUDE.md](../CLAUDE.md) before adding a runtime dependency.

## Notebooks

Select the **Document Copilot Backend** kernel. To register it:

```bash
uv run python -m ipykernel install --user --name document-copilot-backend --display-name "Document Copilot Backend"
```
