# Phase 3 Specs

Phase 3 产品 Spec。Feature 是最小交付单位；**验收只看该 Feature 的 Test Cases 是否通过**。  
当前 Feature 状态均为 **`draft`**（未 `approved` 不得实现）。

## 怎么读

1. [00-constraints.mdc](../../../.cursor/rules/00-constraints.mdc) — 全项目根本约束（含 Feature ID：`P{n}-F{nn}`）
2. [../01-phase-list.md](../01-phase-list.md) — Phase 索引
3. [01-feature-list.md](01-feature-list.md) — 本 Phase Feature 索引与依赖
4. [features/](features/) — 各 Feature

新建 Feature 时复制 [../_TEMPLATE.md](../_TEMPLATE.md) 到 `features/`，ID 取下一号 `P3-F{nn}`。

## 本 Phase 范围（摘要）

| 能力 | Feature |
|------|---------|
| 生产上线与主 Flow 验收 | P3-F01 |
| 索引质量增强（OCR / 结构） | P3-F02 |
| Portal 搜索 Cursor 风 | P3-F03 |
| Debug Page（纯检索 / Agent 透视） | P3-F04 |

微信登录、SOP 强制验证门禁 → **Phase 4**（见 phase list）。
