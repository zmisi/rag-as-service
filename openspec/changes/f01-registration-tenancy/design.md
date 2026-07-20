## Context

Phase 1 采用 FastAPI（`apps/api`）+ Next.js（`apps/web`）+ PostgreSQL。F01 是首个业务 Feature：主站注册并创建租户。数据模型与 DDL 已在 `docs/specs/phase1/features/F01-registration-tenancy-data-model.md` 与 `scripts/sql/f01_registration_tenancy.sql` 中定义。F01 注册成功需签发会话 cookie（与 F02 同一约定），但登录/登出生命周期由 F02 完整实现。

约束来源：`.cursor/rules/00-constraints.mdc` §2（subdomain）、§3.1–3.2（schema/时间戳）、§4（Email 认证）、`06-repo-layout.mdc`（`/backend/*` 同源反代）。

## Goals / Non-Goals

**Goals:**

- 实现 F01 全部 Test Cases（F01-T01–T08）
- 单事务注册：user + tenant + owner member
- subdomain/email 校验与规范化
- 注册 API + 主站注册页 + 重定向/cookie
- Alembic 迁移对齐已有 SQL 脚本

**Non-Goals:**

- 微信注册、密码重置、邮箱验证
- 登录/登出完整流程（F02，但注册需最小 session 集成）
- 文档、聊天、Agent、向量索引
- subdomain 注册后修改
- 租户 Host 鉴权中间件完整实现（F02；F01 e2e 仅需 cookie + redirect）

## Decisions

### 1. API 路径与 Host 约束

- **Decision**: `POST /backend/api/v1/auth/register`（或等价 v1 路径）；middleware 校验 `Host` 为 `lxzxai.com`（本地开发允许配置的 apex host）。
- **Rationale**: 与 `06-repo-layout` 同源 `/backend` 一致；注册仅主站。
- **Alternative**: 独立 `/register` 页面 server action 直写 DB — 违反分层，不采用。

### 2. 分层结构（`apps/api`）

```
api/v1/auth.py          → HTTP 层
services/registration   → 用例编排（校验 → hash → 事务）
domain/tenancy          → subdomain 规则、保留字、规范化
repositories/           → users, tenants, tenant_members CRUD
db/models               → SQLAlchemy ORM（schema=rag_service）
```

- **Rationale**: 与 `architecture.md` 一致；domain 无 IO，便于 unit 测 subdomain 规则。

### 3. 密码哈希

- **Decision**: argon2（`argon2-cffi`）优先；bcrypt 可接受。
- **Rationale**: constraints §3 与 F01 规则 5。

### 4. Subdomain 校验双层

- **Decision**: 应用层完整校验（格式 + 保留字 + 唯一性）；DB CHECK 仅格式/长度（已有 DDL）。
- **Rationale**: 保留字在应用层拒绝便于扩展；DB UNIQUE 保证并发（F01-T08）。

### 5. 注册事务顺序

- **Decision**: 单 transaction：`INSERT users` → `INSERT tenants` → `INSERT tenant_members(role='owner')`；任一步 IntegrityError → rollback。
- **Rationale**: F01 data-model §2；避免 orphan 记录。

### 6. 会话签发（F01 最小集成）

- **Decision**: 注册成功后调用共享 `SessionService.create_session(user_id)` 写 `sessions` 表（F02 同表）并 Set-Cookie；若 F02 未就绪，可先实现最小 session 模块供 F01/F02 共用。
- **Rationale**: F01-T07 要求 Set-Cookie；F02 spec 明确注册在 F01。
- **Alternative**: 注册仅 201 JSON 不重定向 — 不符合 F01-T07 e2e。

### 7. 前端注册页

- **Decision**: `apps/web/app/(main)/register/page.tsx`；表单 POST 至 `/backend/api/v1/auth/register`；成功时浏览器跟随 302。
- **Rationale**: 主站路由；同源 cookie。

### 8. 数据库迁移

- **Decision**: Alembic revision 内容与 `scripts/sql/f01_registration_tenancy.sql` 等价；CI/本地可用 SQL 脚本或 alembic upgrade。
- **Rationale**: SQL 脚本已 review；迁移为 apply 标准路径。

### 9. 测试策略

| 类型 | 范围 |
|------|------|
| unit | subdomain 规则、email 规范化、密码长度 |
| api | F01-T01–T06, T08（TestClient + 测试 DB） |
| e2e | F01-T07（Playwright；Host header + cookie Domain） |

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| F01 依赖 F02 session 表未建 | 本 change 同时引入最小 `sessions` 迁移或 stub SessionService |
| 并发 subdomain 竞态 | DB UNIQUE + 捕获 IntegrityError → 4xx「已被占用」 |
| 本地多子域 cookie 测不通 | Caddy/Next rewrites + `/etc/hosts`；e2e 注入 Host |
| Feature Spec 仍为 `review` | 实现以 Spec Test Cases 为准；上线前需 Spec 转 `approved` |

## Migration Plan

1. 执行 Alembic upgrade（或 `psql -f scripts/sql/f01_registration_tenancy.sql`）
2. 部署 API + Web
3. 验证主站 `/register` 与 F01-T01 smoke
4. Rollback：down migration drop F01 表（仅无下游数据时）

## Open Questions

- F01 与 F02 是否同一 change 实现 session，还是 F01 change 仅含 sessions 表 + 最小签发？**建议**：本 change 含 sessions 表 DDL + 最小 SessionService，F02 补全 login/logout/TTL。
- `apps/api` 脚手架是否已存在？若否，tasks 首项为 monorepo 最小脚手架。
