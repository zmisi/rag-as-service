# 本地多子域开发

Phase 1 注册/登录在主站 `lxzxai.com`；租户站在 `{subdomain}.lxzxai.com`。

## /etc/hosts（示例）

```text
127.0.0.1 lxzxai.com
127.0.0.1 acme.lxzxai.com
```

## Docker Compose

```bash
# 仓库根目录
cp deploy/.env.example .env
docker compose -f deploy/docker-compose.yml up --build
```

服务：

| 服务 | 说明 | 端口 |
|------|------|------|
| `db` | PostgreSQL 16 + pgvector | 5432 |
| `api` | FastAPI；`AUTO_MIGRATE=true` 自动迁移 | 8000 |
| `web` | Next.js；`/backend/*` → `api:8000` | 3000 |

访问：http://lxzxai.com:3000/register

API 容器内 `DATABASE_URL` 指向 `db:5432`（compose 自动注入，无需手改）。

开发时挂载了源码目录，改 `apps/api/src` / `apps/web` 可热更新。

## 原生进程（不用 Docker）

```bash
# 终端 1 — API
cd apps/api && source .venv/bin/activate
uvicorn rag_api.main:app --reload --port 8000

# 终端 2 — Web
cd apps/web && npm run dev
```

访问：http://lxzxai.com:3000/register（`localhost` 仅可看 UI；注册 API 需 `Host: lxzxai.com`）。

E2E：`E2E_ENABLED=1` + `DATABASE_URL` 后 `cd apps/web && npm run test:e2e`。
