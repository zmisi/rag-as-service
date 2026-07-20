## 1. 脚手架与配置

- [x] 1.1 初始化 `apps/api`：FastAPI 入口、`pyproject.toml`、Pydantic Settings（`DATABASE_URL`、cookie 名、apex host）
- [x] 1.2 初始化 `apps/web`：Next.js App Router、 `/backend/*` rewrite 至 API
- [x] 1.3 添加 `.env.example`（DB、SECRET、COOKIE 相关占位）
- [x] 1.4 配置 pytest + TestClient；e2e 框架（Playwright）骨架

## 2. 数据库迁移

- [x] 2.1 配置 Alembic（`search_path=rag_service,public`）
- [x] 2.2 首版 migration：`pgcrypto`、`rag_service` schema、`f_common_update_at()`、`users` / `tenants` / `tenant_members`（对齐 `scripts/sql/f01_registration_tenancy.sql`）
- [x] 2.3 最小 `sessions` 表 migration（F01-T07 cookie 签发；字段对齐 F02 data-model）
- [x] 2.4 schema 测试：insert 后 `create_at`/`update_at` 非空；update 后仅 `update_at` 前进（constraints §3.2）

## 3. ORM 与 Repository

- [x] 3.1 SQLAlchemy models：`User`、`Tenant`、`TenantMember`（schema=`rag_service`）
- [x] 3.2 Repositories：`UserRepository`、`TenantRepository`、`TenantMemberRepository`（create/find_by_email/find_by_subdomain）
- [x] 3.3 注册用例单事务封装：`RegistrationRepository.register_owner(...)` 或 service 内 explicit transaction

## 4. Domain 校验

- [x] 4.1 `domain/tenancy/subdomain.py`：格式、长度、保留字、小写规范化
- [x] 4.2 `domain/identity/email.py`：小写规范化
- [x] 4.3 `domain/identity/password.py`：最小长度 8、argon2 hash/verify
- [x] 4.4 unit tests：subdomain 合法/非法/保留字；email 规范化；密码长度

## 5. Session 最小集成（F01 依赖）

- [x] 5.1 `Session` model + `SessionRepository`
- [x] 5.2 `SessionService.create_session(user_id)`：写 token_hash、expires_at（TTL 14 天）、Set-Cookie（`Domain=.lxzxai.com`, `Secure`, `HttpOnly`, `SameSite=Lax`）
- [x] 5.3 注册成功路径调用 SessionService

## 6. Registration API

- [x] 6.1 Pydantic schemas：`RegisterRequest`（email, password, subdomain）、错误响应
- [x] 6.2 `POST /api/v1/auth/register`：Host 限主站 middleware
- [x] 6.3 `RegistrationService.register`：校验 → hash → 事务 → session → 302 Location `https://{subdomain}.lxzxai.com/admin`
- [x] 6.4 错误映射：格式/保留字/占用/email 重复 → 4xx；IntegrityError → subdomain 占用
- [x] 6.5 结构化日志（注册成功/失败原因）

## 7. API 自动化测试（F01-T01–T06, T08）

- [x] 7.1 F01-T01：合法注册 201；DB 三表 + owner
- [x] 7.2 F01-T02：subdomain `Acme-Co` → 存 `acme-co`
- [x] 7.3 F01-T03：subdomain `ab` → 4xx；无 tenant
- [x] 7.4 F01-T04：subdomain `admin` → 4xx；无 tenant
- [x] 7.5 F01-T05：subdomain 占用 → 4xx；无新 tenant
- [x] 7.6 F01-T06：email 重复 → 4xx；无 tenant
- [x] 7.7 F01-T08：并发同 subdomain → 一成功一失败；DB 仅一条 tenant

## 8. 前端注册页

- [x] 8.1 `apps/web` 主站 layout（`lxzxai.com`）
- [x] 8.2 `/register` 页面：email、password、subdomain 表单 + 客户端基础校验
- [x] 8.3 提交至 `/backend/api/v1/auth/register`；处理 302 跟随
- [x] 8.4 错误态展示（格式、保留字、占用、email 已存在）

## 9. E2E 测试

- [x] 9.1 F01-T07：合法注册 → Location=`https://{subdomain}.lxzxai.com/admin`；Set-Cookie Domain 含 `.lxzxai.com`
- [x] 9.2 本地 hosts / 反代文档或 compose 片段（可选，便于 e2e 跑通）

## 10. 收尾

- [x] 10.1 README：本地启动、迁移、跑 F01 测试
- [x] 10.2 确认 F01 Feature Spec Test Cases 全部有对应自动化测试
- [ ] 10.3 （Spec 流程）F01 status `review` → `approved` → 实现完成后 → `done`
