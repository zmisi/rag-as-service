# P2-F05 Embed Widget

> 提供可嵌入客户 App/页面的聊天 Widget；公开 site key + Origin 白名单，走租户问答能力。

| 字段 | 值 |
|------|-----|
| **Status** | `done` |
| **Owner** | |
| **Approved by** | |
| **Approved at** | 2026-07-24 |

> Status：`draft` → `review` → `approved` → `done`。未 `approved` 不得实现，见 [00-constraints.mdc](../../../../.cursor/rules/00-constraints.mdc) §8。

## 范围

- Admin 生成 **site key**（公开，可出现在前端）与 **允许 Origin 列表**
- 托管脚本：`https://{subdomain}.lxzxai.com/widget.js`（或 CDN 同源等价）
- 嵌入方式：脚本自动挂载 **浮层**（float panel）；提供可复制 snippet
- Widget 内发问走后端（经 site key + Origin 校验），**复用 P1-F06 Agent**（`run_user_turn`）；语义对齐 P1-F06 chat（**不**要求 P2-F04 `rk_live_`；**不**把服务端 Key 下发给浏览器）
- 可配置：主题色、欢迎语、默认打开/关闭（`data-theme-color` / `data-welcome` / `data-open`，默认关闭）
- 租户 harness：`{subdomain}.lxzxai.com/widget` 模拟客户页，加载真实 snippet 便于本地联调

## 非范围

- 原生 iOS/Android SDK（可用 WebView 嵌同一 widget）
- 自定义 CSS 任意注入（防 XSS：仅允许受控主题 token）
- 用 API Key 代替 site key 放进前端
- P2-F04 `{subdomain}.lxzxai.com/api` 与 `rk_live_`（本 Feature 不实现）

## Flow

```mermaid
flowchart TD
  A[客户页加载 widget.js] --> B[带 site_key 初始化]
  B --> C[后端校验 Origin 在白名单]
  C -->|否| E1[拒绝/403]
  C -->|是| D[渲染浮层聊天 UI]
  D --> E[用户发问]
  E --> F[P1-F06 run_user_turn 本租户]
  F --> G[JSON 或 SSE 回复]
```

## 行为规则

1. Site key 绑定 `tenant_id`；与 P2-F04 `api_key` 分表（P2-F04 未实现前仅有本表）；可独立吊销。
2. 每个请求校验 `Origin`/`Referer` 命中白名单（精确 scheme+host[:port]）；未命中 → 403。
3. Snippet 形态固定可测，例如：
   ```html
   <script src="https://{subdomain}.lxzxai.com/widget.js"
           data-site-key="pk_..."
           async></script>
   ```
4. Widget 不得暴露服务端 `rk_live_` Key；浏览器只持 `pk_` site key。
5. 限流：每 site key **30 req/min**（可与 P2-F04 不同）。
6. Admin 可增删白名单 Origin；空白名单 → Widget 全部 Origin 拒绝（安全默认）。
7. `widget.js` API 基址取自脚本 Host（绝对路径 `/backend/v1/widget/...`），避免客户站相对路径误打到客户域名。
8. Widget 会话挂在 `conversations.site_key_id`；`user_id` 为空（与成员会话互斥）。

## 数据与边界

| 实体 | 关键字段 / 约束 |
|------|----------------|
| widget_site_key | `id`, `tenant_id`, `public_key`, `status`, `allowed_origins` text[], `name` |
| conversations | `user_id` 可空；`site_key_id` 可空；CHECK 恰好其一非空 |

## Test Cases

| ID | 步骤 | 期望 | 类型 |
|----|------|------|------|
| P2-F05-T01 | Given admin 创建 site key 并加 Origin `https://app.example.com` When 保存 | Then 可取 `pk_`；白名单含该 Origin | api |
| P2-F05-T02 | Given 合法 Origin + site key When 初始化 Widget 会话/发问 | Then 200；本租户可答 | api |
| P2-F05-T03 | Given Origin 不在白名单 When 发问 | Then 403 | api |
| P2-F05-T04 | Given 错误 site key When 发问 | Then 401 | api |
| P2-F05-T05 | Given site key 吊销 When 发问 | Then 401 | api |
| P2-F05-T06 | Given GET snippet 配置 When admin 复制 | Then 含 `widget.js` 与 `data-site-key` | api |
| P2-F05-T07 | Given 响应/前端包 When 检查 | Then 无 `rk_live_` 字符串 | e2e |
| P2-F05-T08 | Given 租户 Host When GET `/widget` | Then 页面含 widget snippet（`widget.js` + `data-site-key` 占位或真 key） | e2e |
