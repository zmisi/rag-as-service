# 本地多子域开发

Phase 1 注册/登录在主站 `lxzxai.com`；租户站在 `{subdomain}.lxzxai.com`。

## /etc/hosts（示例）

```
127.0.0.1 lxzxai.com
127.0.0.1 acme.lxzxai.com
```

## 进程

```bash
# 终端 1 — API
cd apps/api && source .venv/bin/activate
alembic upgrade head
uvicorn rag_api.main:app --reload --port 8000

# 终端 2 — Web（/backend → API）
cd apps/web && npm run dev
```

访问：`http://lxzxai.com:3000/register`（或 `localhost:3000/register` 做 UI 开发；API 注册需 `Host: lxzxai.com`）。

E2E 全链路：设置 `E2E_ENABLED=1` 与 `DATABASE_URL` 后运行 `npm run test:e2e`。
