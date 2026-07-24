# Phase 2 Specs

Phase 2 产品 Spec。Feature 是最小交付单位；**验收只看该 Feature 的 Test Cases 是否通过**。  
F13 / F14 为 **`done`**；其余 Feature 仍为 **`draft`**（未 `approved` 不得实现）。

## 怎么读

1. [00-constraints.mdc](../../../.cursor/rules/00-constraints.mdc) — 全项目根本约束
2. [../01-phase-list.md](../01-phase-list.md) — Phase 索引
3. [01-feature-list.md](01-feature-list.md) — 本 Phase Feature 索引与依赖
4. [features/](features/) — 各 Feature（flow + 行为规则 + test cases）

新建 Feature 时复制 [../_TEMPLATE.md](../_TEMPLATE.md) 到 `features/`。

## 本 Phase 范围（摘要）

| 能力 | Feature |
|------|---------|
| Office OOXML（`.docx` / `.xlsx` / `.pptx`）上传与索引 | F08 |
| Admin 文件夹树 | F09 |
| 文档预览 | F10 |
| 对外 API + API Key | F11 |
| Embed Widget | F12 |
| Portal FAQ 推荐 | F13 |
| Portal 壳与延迟会话 | F14 |

微信登录、SOP 强制验证门禁 → **Phase 3**（见 phase list）。
