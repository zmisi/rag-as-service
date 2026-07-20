# SQL scripts (deprecated)

Schema is managed by **Alembic** under [`apps/api/alembic/`](../../apps/api/alembic/).

- F01 registration / tenancy: `apps/api/alembic/versions/20260720_f01_registration_tenancy.py`
- API startup runs `alembic upgrade head` when `AUTO_MIGRATE=true` (default).

Do not add new hand-run DDL here; add an Alembic revision instead.
