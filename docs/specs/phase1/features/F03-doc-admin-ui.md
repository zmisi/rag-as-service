# F03 文档管理 Admin UI

> `{subdomain}.lxzxai.com/admin` 租户文档管理工作台的信息架构、组件与交互设计。  
> 业务规则与 API 验收以 [F03-doc-admin.md](F03-doc-admin.md) 为准；本文为 UI 补充 Spec。


| 字段 | 值 |
|------|-----|
| **Status** | `done` |
| **Owner** | |
| **Approved by** | team |
| **Approved at** | 2026-07-21 |
| **Depends on** | F02（会话鉴权）、[F03-doc-admin.md](F03-doc-admin.md)（文档状态机/API） |

## 范围

- `/admin` 页面布局与双栏工作台
- 文档列表（Tag 过滤、搜索、新建）
- 文档 Editor（状态机 Stepper、Save / Submit for Review / Publish）
- 文件上传前端校验（类型、20MB）
- 发布后索引状态只读反馈（F04 数据，不做解析 UI）

## 非范围

- 文档 CRUD API 与状态机后端逻辑（见 F03-doc-admin）
- 解析/分块/embedding 细节 UI（F04）
- 全文预览、版本 diff、检索验证入口
- 正文粘贴（Phase 1 仅文件上传；F03 后端虽允许「文件或正文」）
- 移动端适配（Phase 1 桌面优先）

## 目标与约束

- 状态机必须在 UI 显式体现，禁止跳步：`draft → review → published`
- Tag 受控枚举：`news` | `sop` | `best_practice` | `knowledge_base` | `faq`
- 版本：首次 publish = `1.0`；再编辑 publish 递增 minor +0.1（如 1.0 → 1.1）
- 文件：`.txt` / `.md` / `.pdf`；单文件 ≤ 20MB（Office OOXML 见 Phase 2 F08；不支持旧版 `.doc` / `.ppt`）
- 风格：复用聊天页双栏模式（`apps/web/components/chat/ChatWorkspace.tsx`）

## 页面布局

双栏工作台，桌面优先：

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ 知识库管理                                                                   │
├───────────────────────┬──────────────────────────────────────────────────────┤
│ 文档列表（Sidebar）   │ 文档详情（Main Panel）                               │
│                       │                                                      │
│ [ + 新建文档 ]        │ 进度：[草稿] ─ [待发布] ─ [已发布]                     │
│ 搜索框                │                                                      │
│ Tag Tabs: All / …     │ ┌ 基本信息 ────────────────────────────────────────┐ │
│ 文档行列表            │ │ Title / Tag / 文件上传 / 文件列表 / 校验提示     │ │
│                       │ └ 操作栏：保存草稿 | 提交审核 | 发布 ──────────────────────┘ │
│                       │ ┌ 版本信息（可选） ────────────────────────────────┐ │
│                       │ └ 索引状态（只读，F04 反馈） ──────────────────────┘ │
└───────────────────────┴──────────────────────────────────────────────────────┘
```

入口 `{subdomain}.lxzxai.com/admin`；未登录时 401/403 → 重定向主站 `/login`（F02）。

## 用户流程详解（上传 → 审核 → 发布）

### 三步与 UI 对应

| 阶段 | Stepper 标签（中文） | 主按钮 | 用户心智 |
|------|---------------------|--------|----------|
| 上传文档 | **草稿** | 保存草稿、提交审核 | 「先把文件传上来，信息可以慢慢填」 |
| 审核/校验 | **待发布** | 发布 | 「检查无误了，准备上线」 |
| 发布 | **已发布** | 编辑新版本 | 「已经进知识库，RAG 能搜到」 |

> Stepper 英文枚举仍为 `draft` / `review` / `published`；界面文案建议用中文上表。

### 流程 A：首次上传并发布（ happy path ）

```text
1. [Sidebar] 点「新建文档」
   → 右侧空白 Editor，Stepper 在「草稿」

2. [Editor] 拖拽/选择 pdf，填 Title、选 Tag=FAQ
   → 文件列表出现一行，前端标记 valid

3. [Editor] 点「保存草稿」
   → Toast/静默成功；列表新增一行 badge=草稿；Stepper 仍在草稿

4. [Editor] 点「提交审核」
   → 前端校验通过 → API → Stepper 到「待发布」
   → 表单变为只读（或字段 disabled）

5. [Editor] 点「发布」→ Confirm 弹窗
   → 展示：标题、Tag、version=1.0、文件数、索引说明
   → 用户确认

6. [Editor] 发布成功
   → Stepper 到「已发布」；version 显示 1.0
   → IndexJobStatusCard：索引中… → 索引成功（或失败见流程 C）
   → 主按钮变为「编辑新版本」
```

### 流程 B：分步填写（先传文件，后补标题）

```text
1. 新建 → 只上传文件，不填 Title
2. 保存草稿 → 成功，仍为草稿（F03-T01）
3. 提交审核 → ValidationPanel：「请填写文档标题」→ 仍为草稿（F03-T03）
4. 补 Title、Tag → 保存草稿 → 再提交审核 → 进入待发布（F03-T04）
5. 发布 → 已发布（F03-T05）
```

### 流程 C：发布成功但索引失败

```text
1. 发布成功 → status=published，Stepper=已发布
2. IndexJobStatusCard → failed + error 摘要（如「无法解析 PDF」）
3. 文档在 Admin 仍显示「已发布」，但 RAG 检索不到内容（F04 行为）
4. Phase 1 UI 仅展示失败原因，不提供「重试索引」按钮
```

### 流程 D：已发布后再改一版

```text
1. 选中已发布文档 v1.0 → Stepper=已发布，索引 succeeded
2. 点「编辑新版本」→ 创建 draft，Stepper 回到草稿，version 目标 1.1
3. 换文件 / 改 Title → 保存草稿 → 提交审核 → 发布
4. 成功后 version=1.1；索引区重新 polling；旧 v1.0 chunk 由 F04 下线
```

### 各阶段界面状态

#### 草稿（draft）

| 区域 | 状态 |
|------|------|
| Title / Tag | 可编辑 |
| 文件上传 | 可增删 |
| ValidationPanel | 隐藏（提交审核失败后才显示） |
| 操作栏 | **保存草稿**（secondary）、**提交审核**（primary） |
| Publish | hidden / disabled |
| IndexJobStatusCard | 隐藏或显示「尚未发布」 |

#### 待发布（review）

| 区域 | 状态 |
|------|------|
| Title / Tag / 文件列表 | 只读展示 |
| ValidationPanel | 隐藏 |
| 操作栏 | **发布**（primary，带 confirm） |
| 修改任意字段 | 提示「将回退为草稿」→ 确认后 status=draft，恢复可编辑 |

#### 已发布（published）

| 区域 | 状态 |
|------|------|
| 元数据与文件 | 只读 |
| DocVersionPanel | 显示当前 version |
| IndexJobStatusCard | 显示最新索引 job 状态 |
| 操作栏 | **编辑新版本** |

### 按钮文案与优先级

| API 动作 | 按钮文案（中文） | 样式 | 可用 status |
|----------|------------------|------|-------------|
| Save | 保存草稿 | secondary | draft |
| Submit for Review | 提交审核 | primary | draft |
| Publish | 发布 | primary | review |
| New Version | 编辑新版本 | primary | published |

请求进行中：对应按钮文案改为「保存中…」「提交中…」「发布中…」，全部 action disabled。

### Confirm 弹窗（发布）

```text
标题：确认发布文档？
正文：
  · 标题：{title}
  · 分类：{tag 展示名}
  · 版本：{version，首版为 1.0}
  · 文件：{n} 个
  · 发布后将建立知识库索引，供 AI 问答检索。
按钮：[取消]  [确认发布]
```

### 错误展示位置

| 错误类型 | 展示位置 |
|----------|----------|
| 提交审核缺字段 | `DocValidationPanel`（字段级列表） |
| 文件类型/大小 | 文件列表行内 + 上传区下方 |
| API 网络/5xx | Main Panel 顶部 alert |
| 索引失败 | `IndexJobStatusCard` 内 error 文案 |

## 组件树

```text
AdminPage                          apps/web/app/(tenant)/admin/page.tsx
└── DocAdminWorkspace              apps/web/components/admin/DocAdminWorkspace.tsx
    ├── DocSidebar
    │   ├── DocSidebarHeader       （标题 +「新建文档」）
    │   ├── DocTagTabs             （All + 五类 Tag）
    │   ├── DocSearchBox           （按 title 前端过滤）
    │   └── DocList
    │       └── DocListItem        （title / status badge / version / update_at）
    └── DocMainPanel
        ├── DocMainHeader          （当前文档 title + status）
        ├── DocStatusStepper       （三步进度条，高亮当前步）
        ├── DocEditor
        │   ├── DocMetaForm        （Title 输入、Tag 下拉）
        │   ├── DocFileUploader    （选择文件、前端校验）
        │   ├── DocFileList        （filename / type / size / 校验状态）
        │   ├── DocValidationPanel （Submit for Review 缺失项提示）
        │   └── DocActionBar       （保存草稿 / 提交审核 / 发布 / 编辑新版本）
        ├── DocVersionPanel        （当前 version；有 API 时可扩展历史）
        └── IndexJobStatusCard     （pending/running/succeeded/failed，只读）
```

## 左侧文档列表

| 元素 | 说明 |
|------|------|
| **新建文档** | 创建 draft 文档并在右侧打开 Editor |
| **搜索框** | 按 `title` 前端过滤（Phase 1 不做服务端搜索） |
| **Tag Tabs** | `全部` + `公告动态` / `标准操作规程` / `最佳实践` / `知识库` / `常见问题`（对应 F03-T11） |
| **列表行字段** | `title`（主）、`status` badge、`version`、`update_at` |
| **行点击** | 选中并在右侧加载该文档详情 |

列表行 **不** 暴露与当前 status 不符的快捷动作（如 draft 行不出现 Publish）；主要动作集中在右侧 Editor。

## 状态机与操作栏

UI 必须用 Stepper 显式展示三步，且 **禁止跳步**（对应 F03-T02）：

| status | Stepper 高亮 | 可用 CTA | 禁用/隐藏 |
|--------|--------------|----------|-----------|
| `draft` | Draft | **Save**、**Submit for Review** | Publish |
| `review` | Review | **Publish**（需 confirm） | Save、Submit for Review（除非编辑内容回退 draft，见下） |
| `published` | Published | **编辑新版本**（创建新 draft） | Save / Submit for Review / Publish |

### Save（draft，status 不变）

- 持久化 title、tag、已选文件；**status 保持 `draft`**。
- Phase 1：不强制 title/tag/文件齐全（F03-T01）。
- 文件类型/大小仍在前端与后端校验（F03-T06～T08）。

### Submit for Review（draft → review）

- 前端预检并展示缺失项（与后端 4xx 文案一致）：
  - title 必填
  - tag 必填
  - 至少一份源文件
- 失败：保持 `draft`，在 `DocValidationPanel` 展示错误（F03-T03）。
- 成功：status → `review`（F03-T04）。

### Publish（review → published）

- 仅 `review` 时可点。
- **Publish confirm 弹窗**：展示 document id、即将发布的 version、tag、文件数量；提示「发布后将触发索引任务（F04）」。
- 成功：status → `published`；version 首次为 `1.0`（F03-T05）；刷新 `IndexJobStatusCard`。
- draft 直接 publish：按钮不可用 + 若强行调用 API 则 4xx（F03-T02）。

### review 中编辑

- 若用户在 `review` 修改 title、tag 或文件：status 回退为 `draft`，Stepper 回到 Draft；须重新 Submit for Review。

### 已发布再编辑（published → 新 draft）

- 「编辑新版本」：后端创建新版本 draft，UI 重新进入 Editor 流程。
- 再次 publish 后 version 递增，如 1.0 → 1.1（F03-T10）；Stepper 与 version 面板同步更新。

## Editor 表单

| 字段 | 控件 | 规则 |
|------|------|------|
| Title | 文本输入 | 提交审核时必填 |
| Tag | 受控下拉 | 枚举见下表；非法值 4xx（F03-T06） |
| 源文件 | 文件上传（支持多文件） | 见下表 |

### 字段中文说明（Title / Tag）

#### Title（文档标题）

| 项 | 中文 |
|----|------|
| **字段标签** | 文档标题 |
| **占位符** | 例如：产品使用手册 v2.0 |
| **帮助文案** | 用一句话说明这份资料是什么，便于在列表中识别；不必与上传文件名相同。 |

**填写建议：**

- 写业务能看懂的名称，避免「文档1」「新建 PDF」等泛称。
- 可含主题 + 版本/时间，如「2026 Q3 产品更新说明」「退款政策与操作流程」。
- 多文件同一主题时，title 描述整包含义，如「新员工 onboarding 资料包」。

**示例：**

| 上传文件名 | 推荐标题 |
|------------|----------|
| `product_manual_v2.pdf` | 产品使用手册 v2.0 |
| `Q3_update.pdf` | 2026 Q3 产品更新说明 |
| `refund_policy.md` | 退款政策与操作流程 |


#### Tag（文档分类）

下拉选项固定五类；**存储值**（API）与 **界面展示** 对照：

| 存储值 `tag` | 界面展示名 | 中文说明 | 适用内容示例 |
|--------------|------------|----------|--------------|
| `news` | 公告动态 | 对外或对内发布的通知、新闻、版本更新、活动说明 | 《7 月系统维护通知》《V2 版本发布公告》 |
| `sop` | 标准操作规程 | 必须按步骤执行的操作流程（Phase 2 将加强 SOP 校验） | 《客服退款 SOP》《故障排查标准流程》 |
| `best_practice` | 最佳实践 | 经验总结、推荐做法，非强制流程 | 《大促客服话术建议》《文档命名规范建议》 |
| `knowledge_base` | 知识库 | 通用参考文档、产品/技术说明、背景资料 | 《平台功能介绍》《API 集成指南》 |
| `faq` | 常见问题 | 问答形式或短条目说明，回答「常问的问题」 | 《支持哪些文件格式？》《会话数据保留多久？》 |

**选型速查：**

```text
要按步骤执行？         → 标准操作规程（sop）
是公告/动态？          → 公告动态（news）
是「建议这样做」？     → 最佳实践（best_practice）
是「用户常问的问题」？ → 常见问题（faq）
以上都不像           → 知识库（knowledge_base，默认兜底）
```

**UI 实现约定：**

- 表单标签：**文档标题**、**文档分类**。
- Tag 下拉：展示「界面展示名 + 简短说明」（如 `标准操作规程 — 必须按步骤执行的操作流程`），提交 API 时仍传存储值。
- 左侧 Tag Tabs 与上表「界面展示名」一致：`全部` / `公告动态` / `标准操作规程` / `最佳实践` / `知识库` / `常见问题`。
- Phase 1 检索以文件正文为主；分类主要用于 Admin 列表筛选，不承诺按 tag 限制 RAG 范围。

### 文件上传（前端先校验）

| 规则 | UI 行为 |
|------|---------|
| 允许扩展名 | `.txt` `.md` `.pdf`（Office OOXML 见 F08） |
| 单文件 ≤ 20MB | 超限拒绝并提示（F03-T08） |
| 不支持类型（如 `.exe`） | 拒绝并提示（F03-T07） |
| Office / 旧版 | Phase 1 拒绝 `.doc` / `.ppt` / `.docx` / `.pptx` / `.xlsx`（F03-T07b）；F08 启用 OOXML |
| 上传列表 | 每行：filename、content_type、size、校验状态（valid/rejected） |

## 索引反馈（只读，F04）

位于 Main Panel 底部 `IndexJobStatusCard`，**不做**解析/分块/embedding 细节 UI。

| 字段 | 展示 |
|------|------|
| `status` | pending / running / succeeded / failed |
| `error` | failed 时展示摘要 |
| `attempt_count` | 可选展示 |
| 刷新时机 | Publish 成功后立即请求一次；`pending`/`running` 时每 3s 轮询，终态停止 |

Phase 1 不提供「重试索引」按钮（F04 若有手动重试 API 再扩展）。

## 前端最小数据结构

与后端 API 对齐时使用以下 TypeScript 形状（命名供实现参考）：

```typescript
type DocStatus = "draft" | "review" | "published";
type DocTag = "news" | "sop" | "best_practice" | "knowledge_base" | "faq";

type DocSummary = {
  id: string;
  title: string;
  tag: DocTag;
  status: DocStatus;
  version: string;
  update_at: string;
};

type DocFile = {
  id?: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  validation_state?: "valid" | "rejected";
};

type DocDetail = DocSummary & {
  files: DocFile[];
};

type IndexJobStatus = {
  status: "pending" | "running" | "succeeded" | "failed";
  error?: string | null;
  attempt_count?: number;
  create_at?: string;
  update_at?: string;
};
```

**列表 API 最少返回**：`id, title, tag, status, version, update_at`  
**详情 API 最少返回**：上述 + `files[]`  
**索引状态 API 最少返回**：`status, error, attempt_count`（及时间戳）

## UX 指南

| 场景 | 规则 |
|------|------|
| 未登录 | 401/403 → 重定向主站 `/login`（F02） |
| 请求进行中 | 相关 CTA `disabled` + 文案「处理中…」；禁止重复提交 |
| API 错误 | Main Panel 顶部 `role="alert"` 展示；Submit for Review 字段错误在 `DocValidationPanel` |
| Publish | 必须 confirm modal |
| 空列表 | Sidebar 展示「暂无文档」+ 突出「新建文档」 |
| 未选文档 | Main Panel 展示占位：「选择或新建文档」 |
| review 编辑 | 修改内容后提示「已回退为草稿，请重新提交审核」 |
| 删除 | Phase 1 可选：列表行菜单「删除」+ confirm（软删除，触发 F04 清索引） |

## 实现分期（建议）

| 阶段 | 目标 | 内容 |
|------|------|------|
| **1. 静态骨架** | 结构对齐 Spec | mock 数据驱动 Workspace / Sidebar / Editor / Stepper / IndexJobStatusCard |
| **2. 半动态交互** | 交互对齐状态机 | 按钮 enable/disable、前端文件校验、Submit for Review 提示、Publish confirm、搜索与 Tag 过滤 |
| **3. 接 API** | 验收 F03 Test Cases | 列表/详情/save/submit-review/publish/index status；替换 mock |

## UI 与 F03 Test Cases 映射

| Test Case | UI 验收点 |
|-----------|-----------|
| F03-T01 | Save 后 status 仍为 draft；文件列表可见 |
| F03-T02 | draft 时 Publish 不可见或 disabled |
| F03-T03 | Submit for Review 缺 title 时 ValidationPanel 提示，仍为 draft |
| F03-T04 | Submit for Review 成功后 Stepper 到 Review |
| F03-T05 | Publish 后 Stepper 到 Published，version 显示 1.0，索引区出现 pending/running |
| F03-T06 | Tag 下拉无非法项；若 API 4xx 则 alert |
| F03-T07 | 选 .exe 前端拒绝 |
| F03-T08 | 选 >20MB 前端拒绝 |
| F03-T09 | API 层（UI 无跨租户入口） |
| F03-T10 | 「编辑新版本」后 version 递增可见 |
| F03-T11 | Tag tab 切换后列表仅显示对应 tag |
