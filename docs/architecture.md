# 架构概览（目标态）

本文描述仓库**目标目录与分层**，供脚手架与 Feature 实现对齐。产品边界与验收以 [`.cursor/rules/00-constraints.mdc`](../.cursor/rules/00-constraints.mdc) 与 [`docs/specs/`](specs/) 为准；布局硬约束见 [`.cursor/rules/06-repo-layout.mdc`](../.cursor/rules/06-repo-layout.mdc)。

栈：FastAPI（`apps/api`）+ 独立 Next.js（`apps/web`）+ PostgreSQL/pgvector + QWen。

## 1. 仓库树

```text
rag-as-service/
├── apps/
│   ├── api/                 # FastAPI：HTTP、索引 worker、RAG Agent
│   └── web/                 # Next.js App Router 前端
├── deploy/                  # Caddy/nginx、compose（本地/生产同构）
├── scripts/                 # 运维与本地辅助（不进业务运行时热路径）
├── docs/
│   ├── architecture.md      # 本文件
│   └── specs/               # Phase / Feature Spec
├── .cursor/rules/           # Cursor 公共规则
├── .env.example
└── README.md
```

- 业务代码只落在 `apps/*`；禁止在仓库根散落 Python/TS 业务包。
- Spec 在 `docs/specs/`；根本约束权威正文在 `.cursor/rules/00-constraints.mdc`。
- `scripts/`：迁移封装、种子数据、本地 hosts 检查、一次性修复等；**不**放 Agent prompt（见下方 `prompts/`）。

## 2. 运行拓扑

```text
浏览器
  │  Host: lxzxai.com | {subdomain}.lxzxai.com
  ▼
反代 / Next
  ├─ /*           → apps/web
  └─ /backend/*   → apps/api   （同源，保证 Cookie Domain=.lxzxai.com）
```

| 表面 | 用途 |
|------|------|
| `lxzxai.com` | 注册 / 登录 |
| `{subdomain}.lxzxai.com` | 租户聊天 |
| `{subdomain}.lxzxai.com/admin` | 文档管理 |
| `{subdomain}.lxzxai.com/api` | Phase 2 对外网关（Phase 1 **不做**） |

浏览器只请求同源 `/backend/...`；禁止写死后端内网 `host:port` 作为正式入口。

进程（Phase 1）：

| 进程 | 职责 |
|------|------|
| `api`（uvicorn） | HTTP；publish 只入队 `index_job` |
| `worker`（同包异进程） | 消费 `index_job`：解析 / 分块 / embedding / pgvector |
| `web`（next） | UI；经 `/backend` 调 API |

对象存储：本地 `apps/api/var/storage/`（gitignore），路径由配置注入。

## 3. `apps/api` 树与分层

包名建议：`rag_api`（或等价单一 package），代码在 `apps/api/src/` 下。

```text
apps/api/
├── pyproject.toml | requirements.txt
├── alembic/ + alembic.ini
├── prompts/                 # Agent / 系统提示词（版本化文本，非埋在代码字符串里）
│   ├── system/              # 默认 system prompt、租户可覆盖时的基线
│   ├── rules/               # 「只依据检索结果作答」等规则片段
│   └── intent/              # 意图分类等（若拆文件）
├── src/rag_api/
│   ├── main.py              # ASGI 入口
│   ├── worker.py            # index_job 消费入口
│   ├── config/              # settings（Pydantic Settings）
│   ├── core/                # security、context、exceptions、handlers
│   ├── domain/              # 无 IO 规则（tenancy、identity 等）
│   ├── db/                  # session、models（ORM）
│   ├── repositories/        # 唯一 DB 访问（查询强制 tenant_id）
│   ├── services/            # 用例编排
│   ├── indexing/            # parse / chunk / embed（供 worker）
│   ├── agent/               # intent / loop / tools；加载 prompts/
│   ├── clients/             # QWen、embedding（可 mock）
│   └── api/
│       ├── app.py
│       ├── middleware/      # Host→tenant、会话、日志
│       ├── dependencies/    # current_user / current_tenant
│       ├── schemas/
│       └── v1/              # auth / documents / conversations / agent ...
├── tests/
│   ├── conftest.py
│   ├── factories.py
│   ├── fixtures/            # 样例文档、固定语料（F04/F06 测试）
│   ├── unit/
│   └── integration/         # 对齐 Spec `Fxx-T*`（api 类）
└── var/storage/             # gitignore
```

### `prompts/` 约定

- 路径固定在 `apps/api/prompts/`，由 `agent/` 在运行时加载；改文案可走 PR，避免只改 Python 字符串难 diff。
- 检索片段仍按 `07-rag-agent` 视为不可信数据，与 system/rules 分文件组装（顺序见 F06）。
- 租户级覆盖（若做）只覆盖允许字段，基线仍来自本目录。

### 依赖方向

```text
api → services → repositories → db
services → domain, core, clients
indexing / agent → services 或 repositories（不反向依赖 api schemas）
```

禁止：`domain` 依赖 FastAPI/SQLAlchemy；`repositories → services`；业务层直接读裸 header 拼租户。

### 路由域（Phase 1）

与 Spec Feature 大致对应：`auth`（F01/F02）、`documents`（F03）、内部 indexing（F04）、`conversations`（F05）、`agent`（F06）。  
HTTP 前缀与反代对齐（例如对外 `/backend/...`）；**不**暴露 Phase 2 的 `{subdomain}.lxzxai.com/api` 整合网关。

## 4. `apps/web` 树

```text
apps/web/
├── app/
│   ├── (main)/              # lxzxai.com：register / login
│   └── (tenant)/            # 租户站：chat、admin
├── components/
├── lib/                     # 仅调用同源 /backend/*
├── e2e/                     # Playwright，对齐 Spec e2e 用例
└── next.config.ts           # rewrites：/backend → api（本地可无独立 Caddy）
```

- 租户身份以 Host + cookie 为准，不以客户端「猜 subdomain」为权威。
- 业务 / RAG 逻辑留在 `apps/api`；Next 仅 UI + 薄 BFF。
- **前后端分离**为硬规则（见 [00-constraints.mdc](../.cursor/rules/00-constraints.mdc) §3.0）：不以 Next 全栈替代 FastAPI。

## 5. 横切约定（摘要）

| 主题 | 约定 |
|------|------|
| 多租户 | Host `subdomain` → `tenant_id`；读写/向量检索强制租户过滤 |
| 会话 | Cookie `Domain=.lxzxai.com`，`Secure` / `HttpOnly` / `SameSite=Lax`；TTL 见 F02 |
| 时间戳 | 全表 `createtime` / `lastmodifiedtime` + DB trigger（constraints §3.1） |
| 迁移 | Alembic（`apps/api/alembic/`）；API 启动默认 `upgrade head`（`AUTO_MIGRATE`） |
| RAG | 仅 `published` 可检索；Agent 常量与工具白名单见 `07-rag-agent` / F04、F06 |
| 测试 | Spec Test Cases 全覆盖；LLM 默认 mock（`08-testing`） |

## 6. 相关文档

| 文档 | 作用 |
|------|------|
| [docs/specs/](specs/) | Feature Spec 与验收 |
| [.cursor/rules/](../.cursor/rules/) | 实现时自动注入的工程约束 |
| [README.md](../README.md) | 项目入口 |

脚手架落地后，若真实目录与本文件不一致，**先改代码对齐本文件，或经两人共识后修订本文件与 `06-repo-layout`**。
