# rag-as-service

RAG as a Service.

- Backend: FastAPI（`apps/api`）
- Frontend: 独立 Next.js（`apps/web`）
- 架构目标态：[docs/architecture.md](docs/architecture.md)
- 协作与 AI 公共规则见 [`.cursor/rules/`](.cursor/rules/)
- 产品 Spec 见 [`docs/specs/`](docs/specs/)

## 本地开发（脚手架）

```bash
# 1. 环境变量
cp .env.example .env

# 2. API
cd apps/api && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn rag_api.main:app --reload --port 8000

# 3. Web（另开终端）
cd apps/web && npm install && npm run dev
```

- 浏览器访问 Web：`http://localhost:3000`
- API 健康检查：`http://localhost:8000/api/health`
- 同源反代：`http://localhost:3000/backend/api/health` → API

## 测试

```bash
# API unit（无 DB）
cd apps/api && pytest -m "not integration"

# API integration（F01-T01–T08，需 DATABASE_URL）
cd apps/api && alembic upgrade head
export DATABASE_URL=postgresql+psycopg://rag_app:password@localhost:5432/rag_service
pytest -m integration

# Web E2E（F01-T07，需 API+DB + E2E_ENABLED=1）
cd apps/web && E2E_ENABLED=1 npm run test:e2e
```

多子域本地说明见 [deploy/local-dev.md](deploy/local-dev.md)。
