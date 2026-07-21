# rag-as-service

RAG as a Service.

- Backend: FastAPI（`apps/api`）
- Frontend: 独立 Next.js（`apps/web`）
- 架构目标态：[docs/architecture.md](docs/architecture.md)
- 协作与 AI 公共规则见 [`.cursor/rules/`](.cursor/rules/)
- 产品 Spec 见 [`docs/specs/`](docs/specs/)

## Docker Compose（推荐）

无需本机安装 PostgreSQL；一键启动 **db + api + web**。

```bash
# 1. 环境变量（仓库根目录）
cp deploy/.env.example .env

# 2. /etc/hosts（注册必须）
# 127.0.0.1 lxzxai.com

# 3. 启动
docker compose -f deploy/docker-compose.yml up --build
```

| 用途 | 地址 |
|------|------|
| 注册页（F01） | http://lxzxai.com:3000/register |
| API 健康检查 | http://localhost:8000/api/health |
| 同源反代 | http://localhost:3000/backend/api/health |

常用命令：

```bash
docker compose -f deploy/docker-compose.yml up -d --build   # 后台
docker compose -f deploy/docker-compose.yml logs -f api
docker compose -f deploy/docker-compose.yml down            # 停止
docker compose -f deploy/docker-compose.yml down -v       # 停止并删 DB 卷
```

说明见 [deploy/local-dev.md](deploy/local-dev.md)。

## 本地开发（原生）

- **PostgreSQL 13+**（需先建库 `lxzxai_rag`）
- **/etc/hosts**：`127.0.0.1 lxzxai.com`

```bash
# 1. 环境变量（仓库根目录）
cp .env.example .env
# 按需改 DATABASE_URL；Homebrew 常用：postgresql+psycopg://$(whoami)@127.0.0.1:5432/lxzxai_rag

# 2. API（终端 1）
cd apps/api && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn rag_api.main:app --reload --port 8000
# 默认 AUTO_MIGRATE=true，启动时自动 alembic upgrade head

# 3. Web（终端 2）
cd apps/web && npm install && npm run dev
```

| 用途 | 地址 |
|------|------|
| 注册页（F01） | http://lxzxai.com:3000/register |
| Web UI（仅看页面） | http://localhost:3000 |
| API 健康检查 | http://localhost:8000/api/health |
| 同源反代 | http://localhost:3000/backend/api/health |

手动迁移（可选，`AUTO_MIGRATE=false` 时）：

```bash
cd apps/api && source .venv/bin/activate && alembic upgrade head
```

多子域、租户 Host 说明见 [deploy/local-dev.md](deploy/local-dev.md)。

## 测试

```bash
# API unit（无 DB）
cd apps/api && source .venv/bin/activate
pytest -m "not integration"

# API integration（F01-T01–T08，需 PostgreSQL + DATABASE_URL）
cd apps/api && source .venv/bin/activate
export DATABASE_URL=postgresql+psycopg://$(whoami)@127.0.0.1:5432/lxzxai_rag
pytest -m integration

# Web E2E（F01-T07；需 API+Web+DB 运行，首次 npx playwright install）
cd apps/web && E2E_ENABLED=1 npm run test:e2e
```
