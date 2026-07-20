# F01 注册与租户子域

> 用户在 `lxzxai.com` 用 Email 注册，自选子域 slug，系统校验后创建租户并绑定 `{slug}.lxzxai.com`。

## 范围

- Email + 密码注册
- 用户编辑租户 `slug`；格式与全局唯一性校验
- 创建 `user`、`tenant`，并建立 owner 关系
- 注册成功后引导至 `{slug}.lxzxai.com/admin`（会话签发见 F02）

## 非范围

- 微信注册（Phase 1.5）
- 登录与会话生命周期细节（F02）
- 文档、聊天、Agent

## Flow

```mermaid
flowchart TD
  A[打开 lxzxai.com/register] --> B[填写 email / password / slug]
  B --> C{slug 格式合法?}
  C -->|否| E1[返回格式错误]
  C -->|是| D{slug 保留字?}
  D -->|是| E2[返回保留字错误]
  D -->|否| F{slug 已存在?}
  F -->|是| E3[返回已被占用]
  F -->|否| G{email 已注册?}
  G -->|是| E4[返回 email 已存在]
  G -->|否| H[创建 user + tenant]
  H --> I[绑定 owner]
  I --> J[签发会话 cookie Domain=.lxzxai.com]
  J --> K[重定向到 slug.lxzxai.com/admin]
```

## 行为规则

1. 注册入口仅在 `lxzxai.com`（主站）。
2. `slug` 规则见 [00-constraints.md](../../00-constraints.md) §2；校验失败不得创建任何租户。
3. `slug` 全局唯一；并发双注册同一 slug 时仅一个成功，另一个得「已被占用」。
4. `email` 全局唯一（大小写不敏感，存储小写）。
5. 密码至少 8 字符；存储为不可逆哈希，禁止明文落库。
6. 注册成功立即创建租户；`tenant.slug` 此后可改规则不在本 Feature（Phase 1：注册时一次选定，不可改）。
7. 注册成功后签发会话（与 F02 同一 cookie 约定），并 HTTP 重定向到 `https://{slug}.lxzxai.com/admin`。

## 数据与边界

| 实体 | 关键字段 / 约束 |
|------|----------------|
| user | `id`, `email` UNIQUE (ci), `password_hash` |
| tenant | `id`, `slug` UNIQUE |
| tenant_member | `tenant_id`, `user_id`, `role=owner`；注册时一条 |

时间戳列 `createtime` / `lastmodifiedtime` 见 [00-constraints.md](../../00-constraints.md) §3.1。

## Test Cases

| ID | 步骤 | 期望 | 类型 |
|----|------|------|------|
| F01-T01 | Given 未使用的 email+slug When POST 注册 | Then 201；存在 user/tenant/owner；响应或后续可解析到该 slug | api |
| F01-T02 | Given slug=`Acme-Co` When 注册 | Then 存为 `acme-co` 或拒绝（实现二选一须固定：Phase 1 **规范化为小写**后存） | api |
| F01-T03 | Given slug=`ab`（过短） When 注册 | Then 4xx；无 tenant 行 | api |
| F01-T04 | Given slug=`admin` When 注册 | Then 4xx 保留字；无 tenant 行 | api |
| F01-T05 | Given slug 已被占用 When 另一 email 注册同 slug | Then 4xx 已被占用；无新 tenant | api |
| F01-T06 | Given email 已注册 When 再注册 | Then 4xx；slug 即使空闲也不创建 tenant | api |
| F01-T07 | Given 合法注册成功 When 跟随重定向 | Then Location 指向 `https://{slug}.lxzxai.com/admin`；Set-Cookie Domain 含 `.lxzxai.com` | e2e |
| F01-T08 | Given 两请求并发同 slug When 同时注册 | Then 恰一成功一失败；DB 中该 slug 仅一条 tenant | api |
