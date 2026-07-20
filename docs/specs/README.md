# Specs

Feature 是最小交付单位；**验收只看该 Feature 的 Test Cases 是否通过**。

## 怎么读

1. [00-constraints.md](00-constraints.md) — 全项目根本约束（不可被 Phase/Feature 绕过）
2. [01-phase-list.md](01-phase-list.md) — Phase 索引
3. 进入对应 Phase → Feature List → Feature Spec

## 目录

| 路径 | 作用 |
|------|------|
| [00-constraints.md](00-constraints.md) | 根本规则 |
| [01-phase-list.md](01-phase-list.md) | Phase 清单 |
| [_TEMPLATE.md](_TEMPLATE.md) | Feature 模板（新建时复制到 `phaseN/features/`） |
| [phase1/](phase1/) | Phase 1 Spec |
| [phase2/](phase2/) | Phase 1.5 / 2 预留 |

## Spec 哲学

| 层级 | 作用 |
|------|------|
| Constraints | 全项目不可违反的边界 |
| Phase | 交付阶段；见 Phase List |
| Feature | 最小单位；mermaid flow 消除理解歧义；状态 `draft`→`review`→`approved`→`done` |
| Test cases | 唯一验收标准 |

**未 `approved` 的 Feature 不得实现**（见 [00-constraints.md](00-constraints.md) §8）。

不做：冗长 PRD、无验收条目的愿景段落。
