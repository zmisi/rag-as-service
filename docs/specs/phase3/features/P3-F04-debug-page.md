# P3-F04 Debug Page

> 租户 Debug 页：① 纯向量/知识检索（不进 LLM）验证索引质量；② 与 Portal 同路径的问答，但展开打印上下文、top-K、历史、LLM 请求与返回，便于排障。

| 字段 | 值 |
|------|-----|
| **Status** | `draft` |
| **Owner** | |
| **Approved by** | |
| **Approved at** | |

> ID：`P3-F04`。依赖 [P1-F04](../../phase1/features/P1-F04-doc-ingestion.md)、[P1-F06](../../phase1/features/P1-F06-rag-agent.md)、[P2-F07](../../phase2/features/P2-F07-portal-shell.md)。未 `approved` 不得实现。

## 范围

- 路由：`{tenant_name}.lxzxai.com/admin/debug`（仅租户成员；与 `/admin` 同会话门禁）
- **模式 A — Search only**：输入 query + `top_k` → 调用与 Portal/Agent 相同的 `search(tenant_id, query, top_k)`（P1-F04）；**不**调用 LLM；页面展示命中列表（path、节全文/摘要、分数若有）
- **模式 B — Agent debug**：输入与 Portal 等价（可带 `conversation_id` 或 draft 首问）；走 P1-F06 Agent Loop；UI **额外**只读面板打印：
  1. 组装后的 **上下文**（system / 规则 / 压缩历史摘要 / 本轮注入片段的结构化视图）
  2. **top-K** 检索原始结果（与模式 A 同形）
  3. **历史消息**（本会话送入模型前的列表）
  4. **LLM 调用信息**（模型名、超时、step、tool_calls 摘要；**禁止**打印 API Key）
  5. **LLM 返回**（各 step 的 raw/规范化 content 与最终 answer）
- 检索语义、租户隔离、published 门禁与 Portal/生产路径一致（同一 `search` / `run_user_turn` 实现，可加 `debug=true` 返回附加字段）

## 非范围

- 对匿名用户或跨租户开放 Debug
- 修改索引算法（P3-F02）或 Portal 正式 UI（P3-F03）
- 在生产对所有租户默认开启；可用环境开关 `ENABLE_ADMIN_DEBUG=true`（默认生产建议 false，Staging/本地 true）
- 持久化 debug dump 到长期表（可选一次性下载 JSON；Phase 3 不强制落库）

## Flow

```mermaid
flowchart TD
  A[成员打开 /admin/debug] --> B{模式}
  B -->|Search only| C[输入 query top_k]
  C --> D[P1-F04 search]
  D --> E[展示 top-K 无 LLM]
  B -->|Agent debug| F[输入问题 可选会话]
  F --> G[P1-F06 run_user_turn debug]
  G --> H[答完 + 打印 context topK history LLM_in LLM_out]
```

## 行为规则

1. 未登录 / 非本租户成员 → 401/403（同 P1-F02 `/admin`）。
2. Search only：**零** LLM HTTP 调用（测试可用 mock 计数断言）。
3. Agent debug：行为结果（最终用户可见回答）须与同输入的 Portal 路径一致（允许时间戳等非功能差异）；debug 面板仅附加信息。
4. Debug 载荷不得包含其他租户数据；`tenant_id` 仅来自 Host/会话。
5. 密钥、完整 `Authorization`、embedding API Key 不得出现在 UI/日志面板。
6. `top_k` 默认与 P1-F06 一致（如 5），页面可改，设上限（如 20）防滥用。
7. 若 `ENABLE_ADMIN_DEBUG=false`：路由 404 或 403（实现固定一种并写进用例）。

## 数据与边界

| 项 | 约束 |
|----|------|
| API（建议） | `POST /v1/admin/debug/search`；`POST /v1/admin/debug/chat`（或 chat + `debug=true`） |
| Search 响应 | `{ hits: [{ path, content, score?, document_id?, section_id? }] }` |
| Chat debug 响应 | 正常 chat 字段 + `debug: { context_messages, top_k_hits, history, llm_calls: [{ step, request_summary, response_summary }] }` |
| 无新业务表 | 可选 |

## Test Cases

| ID | 步骤 | 期望 | 类型 |
|----|------|------|------|
| P3-F04-T01 | Given 成员 + 已索引独特短语 When Search only | Then 命中含该短语；过程无 LLM 调用 | api |
| P3-F04-T02 | Given 未 publish 文档短语 When Search only | Then 不命中 | api |
| P3-F04-T03 | Given tenant-A 语料 When tenant-B Search only | Then 0 命中 | api |
| P3-F04-T04 | Given 成员 When Agent debug 可命中问题 | Then 有最终回答；debug 含 top_k、context、history、至少一次 llm_calls；无 API Key 字符串 | api |
| P3-F04-T05 | Given 未登录 When 访问 `/admin/debug` 或 API | Then 401/302 登录 | e2e |
| P3-F04-T06 | Given `ENABLE_ADMIN_DEBUG=false` When 访问 | Then 404 或 403 | api |
| P3-F04-T07 | Given 同 query When Portal chat vs Agent debug 最终文本 | Then 语义一致（或固定 mock 下逐字一致） | api |
