# Phase 1 Specs

Phase 1 产品 Spec。Feature 是最小交付单位；**验收只看该 Feature 的 Test Cases 是否通过**。

## 怎么读

1. [../00-constraints.md](../00-constraints.md) — 全项目根本约束
2. [../01-phase-list.md](../01-phase-list.md) — Phase 索引
3. [01-feature-list.md](01-feature-list.md) — 本 Phase Feature 索引与依赖
4. [features/](features/) — 各 Feature（flow + 行为规则 + test cases）

新建 Feature 时复制 [../_TEMPLATE.md](../_TEMPLATE.md) 到 `features/`。

## 域名一览

| 表面 | 用途 |
|------|------|
| `lxzxai.com` | 主站：注册 / 登录 |
| `{slug}.lxzxai.com` | 租户 RAG 聊天入口 |
| `{slug}.lxzxai.com/admin` | 租户文档管理 |
