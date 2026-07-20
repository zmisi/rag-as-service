# rag-as-service

RAG as a Service.

- Backend: FastAPI（`apps/api`）
- Frontend: 独立 Next.js（`apps/web`）
- 架构目标态：[docs/architecture.md](docs/architecture.md)
- 协作与 AI 公共规则见 [`.cursor/rules/`](.cursor/rules/)
- 产品 Spec 见 [`docs/specs/`](docs/specs/)

## Backend（本地）

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e apps/api
cp .env.example .env   # 按需改 DATABASE_URL
cd apps/api && uvicorn rag_api.main:app --reload
```

启动时默认跑 `alembic upgrade head`（可用 `AUTO_MIGRATE=false` 关闭）。手动迁移：

```bash
cd apps/api && alembic upgrade head
```
