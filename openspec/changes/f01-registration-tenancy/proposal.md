## Why

Phase 1 多租户 RAG 服务的入口是「用户注册并创建租户」。没有 F01，无法建立 `user` / `tenant` / `owner` 关系，也无法将 `{subdomain}.lxzxai.com` 绑定到租户。F01 是 F02（登录会话）、F03+（租户内业务）的前置能力，需优先落地。

## What Changes

- 新增主站 `lxzxai.com` 注册流程：Email + 密码 + 自选 `subdomain`
- 新增注册 API：校验 subdomain 格式/保留字/唯一性、email 唯一性、密码长度；单事务创建 `users`、`tenants`、`tenant_members(role=owner)`
- 新增 `rag_service` schema 下三张表及 `f_common_update_at` trigger（DDL 已有 `scripts/sql/f01_registration_tenancy.sql`）
- 注册成功后签发会话 cookie（与 F02 同一约定）并重定向至 `https://{subdomain}.lxzxai.com/admin`
- 新增 Next.js 注册页（主站）及 `/backend` 同源 API 调用
- 新增自动化测试覆盖 F01-T01–T08（api + e2e）

## Capabilities

### New Capabilities

- `registration-tenancy`: 主站 Email 注册、subdomain 校验与规范化、租户与用户创建、owner 绑定、注册后重定向与 cookie 签发（会话细节与 F02 对齐）

### Modified Capabilities

（无 — `openspec/specs/` 尚无既有 capability spec）

## Impact

- **数据库**：`rag_service.users`、`tenants`、`tenant_members`；Alembic 迁移或等价迁移封装
- **API**（`apps/api`）：注册 endpoint、domain 校验（subdomain/email/password）、registration service、ORM models/repositories
- **Web**（`apps/web`）：`/register` 页面、表单校验、注册成功后跟随重定向
- **依赖**：PostgreSQL + pgcrypto；密码哈希（argon2/bcrypt）；F02 会话模块最小集成（注册时签发 cookie）
- **Spec 对齐**：`docs/specs/phase1/features/F01-registration-tenancy.md`、F01-data-model、Test Cases F01-T01–T08
