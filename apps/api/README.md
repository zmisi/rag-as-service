# rag-api

FastAPI backend for rag-as-service.

## Setup

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Copy repo root `.env.example` to `.env` and adjust `DATABASE_URL`.

## Migrate

```bash
alembic upgrade head
```

Migrations live in `alembic/versions/`:
- `001` — F01 `users` / `tenants` / `tenant_members`
- `002` — `sessions` (F01 cookie / F02 auth)

## Run

```bash
uvicorn rag_api.main:app --reload --host 0.0.0.0 --port 8000
```

## Test

```bash
pytest                          # unit + api (no DB)
pytest -m integration           # schema/timestamp tests (needs DATABASE_URL)
```
