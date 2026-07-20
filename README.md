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
pip install -e "apps/api[dev]"
cp .env.example .env   # 按需改 DATABASE_URL；本地联调前端时设 AUTH_STUB_ENABLED=true
cd apps/api && uvicorn rag_api.main:app --reload
```

启动时默认跑 `alembic upgrade head`（可用 `AUTO_MIGRATE=false` 关闭）。手动迁移：

```bash
cd apps/api && alembic upgrade head
```

## Frontend（本地，F05 租户聊天）

浏览器走 Next（`:3000`），经 `/backend/*` rewrite 到 API（`:8000`）。**不要**用 `http://127.0.0.1:8000/` 当前端。

1. `/etc/hosts` 增加：

```text
127.0.0.1 tenant-a.lxzxai.com
```

2. 初始化开发租户（幂等）：

```bash
source .venv/bin/activate
python scripts/seed_dev_tenant.py
```

脚本会打印 `NEXT_PUBLIC_DEV_USER_ID=...`。若库里已有 `tenant-a` / `owner-a@example.com`，会直接复用。

或手工查询：

```sql
SELECT u.id, u.email, t.subdomain
FROM rag_service.users u
JOIN rag_service.tenant_members m ON m.user_id = u.id
JOIN rag_service.tenants t ON t.id = m.tenant_id
WHERE t.subdomain = 'tenant-a';
```

3. 根目录 `.env`：

```text
AUTH_STUB_ENABLED=true
```

4. `apps/web/.env.local`（从 `.env.local.example` 复制）：

```text
NEXT_PUBLIC_DEV_USER_ID=<上一步的 users.id>
```

5. 启动前端：

```bash
cd apps/web && npm install && npm run dev
```

6. 打开：`http://tenant-a.lxzxai.com:3000/chat`

开发态鉴权用 `X-Test-User-Id`（`AUTH_STUB_ENABLED`）；正式 cookie 会话见 F02。Agent 回复见 F06——当前聊天页只落库 user 消息。
