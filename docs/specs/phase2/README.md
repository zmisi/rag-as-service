# Phase 1.5 / Phase 2 预留

本目录**不进入 Phase 1 验收**。下列能力仅占位，避免实现时误做进 Phase 1。

Phase 1 Spec 见 [../phase1/](../phase1/)。根本约束见 [00-constraints.mdc](../../../.cursor/rules/00-constraints.mdc)；Phase 索引见 [../01-phase-list.md](../01-phase-list.md)。

## Phase 1.5 — 微信登录

- 在注册/登录流预留第三方身份绑定接口位（如 `auth_provider=wechat`）。
- Phase 1 Test Cases **不要求**微信可登录。
- 落地时新增独立 Feature Spec（建议 F07），含扫码/OAuth flow 与用例。

## Phase 2 — SOP 强制验证门禁

- SOP（`tag=sop`）必须验证成功才能 publish（或上传后不可进入 review）。
- 与 F03 Phase 1「verify = 必填项检查」区分：Phase 2 增加**内容/结构校验**。
- 落地时修订 F03 或新增 Feature，并增加失败不可 publish 的 Test Cases。

## Phase 2 — 对外 API 网关

- 表面：`{subdomain}.lxzxai.com/api`
- 用途：租户将 RAG/能力整合进自有系统（鉴权、限流、稳定契约）。
- Phase 1 不暴露此路径；内部 F04 search / F06 调用不算对外 API。
