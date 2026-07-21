# rag-api

FastAPI backend for rag-as-service.

## Setup

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Copy repo root [`.env.example`](../../.env.example) to `.env` and adjust `DATABASE_URL`.

## Migrate

API 启动默认 `AUTO_MIGRATE=true`，会自动 `alembic upgrade head`。手动迁移：

```bash
cd apps/api && alembic upgrade head
```

Migrations（`alembic/versions/`）：

- `20260720_f01` — F01 `users` / `tenants` / `tenant_members`
- `002` — `sessions`（F01 cookie / F02 auth）

## Run

```bash
uvicorn rag_api.main:app --reload --host 0.0.0.0 --port 8000
```

## Test

```bash
pytest -m "not integration"    # unit，无 DB
pytest -m integration            # 需 DATABASE_URL（conftest 会 migrate）
```
