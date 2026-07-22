# F04 文档索引

> 仅对 `published` 文档解析、按 **H1/H2 节树** 分块、embedding（仅 leaf），写入 PostgreSQL/pgvector；提供内部 **向量检索**（命中 leaf → 返回 **所属节全文 + path**）；按租户隔离。


| 字段 | 值 |
|------|-----|
| **Status** | `done` |
| **Owner** | |
| **Approved by** | |
| **Approved at** | |

> **数据模型依赖**：列名与版本行语义以 [02-data-model.md](../02-data-model.md) 与 [F07-doc-indexing-data-model.md](F07-doc-indexing-data-model.md) 为准（`is_latest` 替代原 `is_active`；`index_status`；`section_index`/`chunk_index`；富 chunk 字段）。本 Feature 索引/检索行为仍有效；持久化重构由 F07 验收。

## 范围

- 消费「文档已 publish」事件（或等价轮询 `index_job`）
- 解析 `.txt` / `.pdf` / `.docx` / `.pptx`（与 F03 一致；不解析旧版 `.doc` / `.ppt`）
- **PDF 双路由解析**：优先 **PyMuPDF** 快速提取文本；质量不足或失败时降级 **Docling**（`do_ocr=false`；表格以 Markdown 表保留）
- **Office 解析**：`.docx` / `.pptx` 固定 **Docling**（Phase 1 不走 PyMuPDF）
- **层级感知切块**：从解析结果构建 **H1 / H2** 节树；更深标题并入最近的 H2 叶节；节内再按可配置 token 切出 leaf chunk
- **仅 leaf** 写入 embedding / pgvector；节全文与 `path` 存于 `document_sections`
- 推进版本行 **`index_status`**：`pending` → `processing` → `ready` / `failed`
- **内部检索** `search(tenant_id, query, top_k)`：`is_latest` leaf 向量 top-k → 组装节全文 + `path`（供 F06 `search_knowledge` 调用）
- 文档软删除或新版本索引成功后：旧 version 的 section / chunk / documents **`is_latest=false`**

## 非范围

- Admin UI 与发布状态机（F03）
- 文档版本行 schema / 双状态列迁移与富 chunk 字段落地（F07）
- Agent 对话与 Agent Loop / `search_knowledge` 工具编排（F06；F06 只调用本 Feature 的 `search`）
- 未 publish 文档的预览索引
- **OCR** / 扫描件文字识别（无文字层 PDF 见行为规则：空成功；双路由 **不** 为扫描件开启 OCR）
- 中文专用 OCR 后端（如 PaddleOCR）、云服务兜底（如 LlamaParse）——留 Phase 1.5+ 评估
- **任意深**目录树（Phase 1 仅 H1/H2）
- Dify 式 Parent-child 的「Full Doc」整篇 parent、或仅扁平 General 切块（无节树）
- 持久化第三方解析器原生对象树（仅落自家 `document_sections` / `document_chunks`）
- 对外 REST 检索网关（Phase 2）

## Flow

```mermaid
flowchart TD
  A[F03 Publish 成功] --> B[入队 index_job / documents.index_status=pending]
  B --> C[worker 抢到 job → index_status=processing]
  C --> D[拉取源文件]
  D --> E{解析成功?}
  E -->|否| E1[job=failed / index_status=failed 可重试]
  E -->|是| S[构建 H1/H2 Section 树]
  S --> F{有可索引文本?}
  F -->|否 空文档/无字 PDF| I0[job=succeeded / index_status=ready 0 section/chunk]
  F -->|是| G[节内切 leaf ChunkDraft]
  G --> H[仅 leaf Embedding]
  H --> W[写入 sections + chunks 绑定 tenant_id is_latest=true]
  W --> I[job=succeeded / index_status=ready]
  I --> J[该版本行可被 search]

  K[软删除或新版本索引完成] --> L[旧版本 documents/sections/chunks is_latest=false]
```

```mermaid
flowchart TD
  subgraph pdf [PDF 双路由·Phase 1]
    P0[.pdf 源文件] --> P1[PyMuPDF 快速探测与提取]
    P1 --> P2{质量达标?}
    P2 -->|是| P3[parse_route=pymupdf]
    P2 -->|否 无字/乱码/失败| P4[Docling do_ocr=false]
    P4 --> P5[parse_route=docling]
    P3 --> P6[Markdown/纯文本]
    P5 --> P6
  end
  subgraph office [Office·Phase 1]
    O0[.docx / .pptx] --> O1[Docling]
    O1 --> O2[parse_route=docling]
  end
  subgraph text [文本]
    T0[.txt / .md] --> T1[文本解码]
    T1 --> T2[parse_route=text]
  end
  P6 --> U[合并 → Section 树]
  O2 --> U
  T2 --> U
```

```mermaid
flowchart LR
  subgraph parse [解析]
    Routes[PyMuPDF / Docling / Text] --> Units[中间结构 → Section 树]
  end
  subgraph chunk [切块]
    Units --> Sec[document_sections 节全文+path]
    Units --> Leaf[document_chunks leaf + embedding]
  end
  subgraph search [检索·本 Feature]
    Q[query embed] --> Hit[top-k leaf is_latest]
    Hit --> Out[返回节全文 + path]
  end
```

## 行为规则

1. **门禁（写）**：`publish_status != published` 的文档不得产生可检索态（`is_latest=true`）的 section / chunk。Publish 入队时版本行 `index_status=pending`。
2. **门禁（读 / search）**：仅当文档同时满足 `publish_status=published` AND `index_status=ready` AND `deleted_at IS NULL` AND leaf/section **`is_latest=true`**，且强制 `tenant_id` 过滤，方可命中。
3. 所有 section / chunk 必须带 `tenant_id`；写库与 **search** 均强制 `tenant_id` 过滤。
4. 同一 `document_group_id` 新版本索引成功后，旧版本 **documents / sections / chunks** **必须** `is_latest=false`（禁止用物理删除作为唯一手段）；软删除文档同理。
5. Worker 状态：抢到 job → `index_status=processing`；成功 → `ready`（并写 documents 上 embedding 审计字段）；失败 → `failed` + `error_message`；job 表 `status` 仍维护（队列视角）。
6. **解析失败**（文件损坏、PyMuPDF 与 Docling 均无法打开/转换等）：job `failed`，文档仍 `published`，`index_status=failed`，无 `is_latest` section/chunk；可重试（Phase 1：至少一条可测重试路径）。
7. **无字 / 空文档**：空 txt、或无文字层且未做 OCR 的 PDF → 解析结果为空 → job **`succeeded`**，`index_status=ready`，**0** section/chunk；search 无命中。（与「损坏失败」区分。）
8. **解析与表结构**：
   - **`.txt` / `.md`**：按字节解码为文本（UTF-8 优先，可回退 gb18030 / latin-1）；`parse_route=text`。
   - **`.pdf`（双路由）**：
     1. **Fast path — PyMuPDF**：逐页快速探测并提取文本（目标 **&lt; 0.1s/页** 量级，无 GPU）；记录 `parse_route=pymupdf`。
     2. **质量判定**（启发式，实现可调阈值经 Settings）：总提取字符数不足、每页平均字符过低、可打印/CJK 字符占比过低、或 PyMuPDF 抛错 → 视为 fast path **未达标**。
     3. **Fallback — Docling**：fast path 未达标时调用 Docling；`do_ocr=false`；表结构提取开启；导出 Markdown 表；`parse_route=docling`。
     4. Docling 未安装且 fast path 未达标 → 按规则 6 **failed**（可测路径：集成环境需装 Docling 或 mock）。
   - **`.docx` / `.pptx`**：固定 Docling（`do_ocr=false`）；`parse_route=docling`。
   - **多文件文档**：按 `document_files` 顺序解析后合并进同一版本的节树（文件间可插入分隔，避免表粘连）；每文件独立选路由并写结构化日志。
9. **节树（层级）**：
   - Phase 1 仅识别 **H1 / H2**（或 Docling/Markdown 等价一级、二级标题）。
   - 更深标题（H3+）**并入**最近的 H2 叶节（无 H2 则并入所属 H1）。
   - 无任何标题：整篇（或整文件合并结果）作为 **单节**，`path` 可用文档 title 或文件名。
   - 若 H1 下存在 H2：叶节以 **H2** 为准；H1 仅含导言、且导言非空时可另成叶节（`path` = 该 H1 标题），否则不单独建空 H1 叶节。
   - 每节存储 **`path`**（如 `退款政策 > 时效`）与 **节全文** `content`（含该节下段落与 Markdown 表）；`level` 为 text `'1'`|`'2'`；序号列 **`section_index`**。
10. **切块（可配置，仅节内）**：
   - 对每个叶节全文再切 leaf：目标长度与重叠经 Settings（默认 `CHUNK_TARGET_TOKENS=800`，`CHUNK_OVERLAP_TOKENS=100`）。
   - **禁止**跨 H2（叶节）边界合并正文后再切。
   - 空节不产生 leaf；整文档无文本 → 0 chunk（见规则 7）。
   - 运行时只读配置；禁止同进程混用多套分块参数写同一批 chunk。
   - leaf 序号列 **`chunk_index`**（文档版本内全局）；写富字段（`heading_path`、`embedding_text`、`chunk_type`、`content_hash` 等）；**不**在 chunk 上存 `embedding_model`。
11. **Embedding（可配置）**：仅对 **leaf** `document_chunks` 调用单一 QWen 兼容接口；模型名与维度经配置（如 `EMBEDDING_MODEL`、`EMBEDDING_DIM`，默认维度 `1024`）。成功后审计字段写在 **`documents`**（`embedding_model` / `embedding_dimension` / provider）。同一部署一套维度；列类型与配置一致；改维度须迁库 + 全量重建。节全文 **不**单独向量化。
12. **检索契约**（本 Feature 实现）：`search(tenant_id, query, top_k) → Hit[]`
    - 用 query embedding 在 **`is_latest` leaf** 上 top-k（且对应文档 `publish_status=published`、`index_status=ready`、未软删）；
    - 每条命中映射到所属叶节，返回至少：`document_id`、`chunk_id`（命中的 leaf id）、`section_id`、`path`、`content`（**节全文**）、`score`；
    - **同一节**因多个 leaf 命中时去重，只保留最高分一条（结果中同一 `section_id` 至多一次）；
    - `tenant_id` 仅来自调用方上下文，禁止由不可信输入覆盖。
13. 旧版本失效策略固定为 **`is_latest=false`**；检索只使用 `is_latest=true` 的 leaf，并只返回对应 `is_latest` 节。
14. **可观测性**：索引 job 成功/失败日志须含 `document_id`、`version`（int）、每源文件的 `parse_route`（`text` | `pymupdf` | `docling`）；Settings 阈值：`PDF_FAST_MIN_CHARS`（默认 80）、`PDF_FAST_MIN_CHARS_PER_PAGE`（40）、`PDF_FAST_MIN_PRINTABLE_RATIO`（0.85）、`PDF_FAST_MAX_EMPTY_PAGE_RATIO`（0.50）。

## 流水线中间对象（实现约定，非对外 API）

| 对象 | 用途 |
|------|------|
| 解析出口 | 映射为自家节树（非 Docling 原生对象直接下游） |
| `parse_route` | 单文件解析路径：`text` / `pymupdf` / `docling`；写结构化日志 |
| 叶节 | 含 `path`、节全文、`section_index`、text `level`；写入 `document_sections` |
| `ChunkDraft` | 节内 leaf：`content` + `chunk_index` + `section` 关联（及 `heading_path` / `embedding_text` 等）；写入 `document_chunks` 并 embed |

## 数据与边界

| 实体 | 关键字段 / 约束 |
|------|----------------|
| documents（版本行，索引相关） | `id`, `tenant_id`, `document_group_id`, `version`（int）, `is_latest`, `publish_status`, `index_status`(`pending`\|`processing`\|`ready`\|`failed`), `error_message`, `embedding_*`（审计） |
| index_job | `id`, `tenant_id`, `document_id`（→ 版本行）, `version`（int）, `status`(`pending`\|`running`\|`succeeded`\|`failed`), `error` |
| document_section | `id`, `tenant_id`, `document_id`, `parent_id`（可选，H2→H1）, `level`（text `'1'`\|`'2'`）, `title`, `path`, `content`（节全文）, `section_index`, `is_latest` |
| document_chunk（leaf） | `id`, `tenant_id`, `document_id`, `section_id`, `chunk_index`, `heading_path`, `content`, `embedding_text`, `chunk_type`, `token_count`, `content_hash`, `embedding vector(EMBEDDING_DIM)`, `metadata_`, `is_latest`（**无** `embedding_model`） |

时间戳列 `create_at` / `update_at` 见 [00-constraints.mdc](../../../../.cursor/rules/00-constraints.mdc) §3.2。明细见 [02-data-model.md](../02-data-model.md)。

内部检索（非对外 Phase 2 API）：

`search(tenant_id, query, top_k) → Hit[]`，其中 `Hit.content` = 节全文，`Hit.path` = 节路径。

**检索门禁**：`publish_status=published` AND `index_status=ready` AND `deleted_at IS NULL` AND section/chunk `is_latest=true` AND `tenant_id` 匹配。

## Test Cases

| ID | 步骤 | 期望 | 类型 |
|----|------|------|------|
| F04-T01 | Given 文档 publish When 索引 job 跑完 | Then job=succeeded；`index_status=ready`；存在 `is_latest` leaf chunks；embedding 非空；存在对应 `is_latest` sections（含非空 `path` 与节 `content`） | api |
| F04-T02 | Given `publish_status`=`review` 未 publish When 强行请求索引 | Then 不产生 `is_latest` section/chunk | api |
| F04-T03 | Given tenant-A 已索引文档 When tenant-B 调用 search 相同 query | Then 0 条 A 的命中 | api |
| F04-T04 | Given 空 txt publish When 索引 | Then job=succeeded；`index_status=ready`；0 section/chunk；search 无命中 | api |
| F04-T05 | Given `version=1` 已索引 When `version=2` 索引成功 | Then 仅 v2 documents/sections/chunks `is_latest=true`；search 不返回 v1 | api |
| F04-T06 | Given 已索引文档软删除 When search | Then 无该文档命中（section/chunk `is_latest=false`） | api |
| F04-T07 | Given 损坏/无法打开文件 When 索引 | Then job=failed；`index_status=failed`；无 `is_latest` section/chunk | api |
| F04-T08 | Given 已索引语料含独特短语 When search 该短语 | Then top-k 命中；返回的 `content` 为节全文且含该短语，`path` 非空 | api |
| F04-T09 | Given 无文字层 PDF（不 OCR）When 索引 | Then job=succeeded；`index_status=ready`；0 section/chunk | api |
| F04-T10 | Given 含 H1 与两个 H2 且各含独特短语的文档 When 索引 | Then leaf 不跨 H2；两节 `path` 可区分；各短语只出现在对应节 `content`；`section_index` 唯一 | api |
| F04-T11 | Given 同上 When search 仅出现在 H2-B 的短语 | Then 命中返回 H2-B 节全文与对应 `path`；`content` 不含 H2-A 专属正文 | api |
| F04-T12 | Given 同节内多 leaf 均可被同一 query 命中 When search | Then 同一 `section_id` 在结果中至多出现一次 | api |
| F04-T13 | Given 含可提取文字层的 PDF（独特短语）When 索引 | Then job=succeeded；走 PyMuPDF fast path（`parse_route=pymupdf` 或等价可测信号）；search 可命中该短语 | unit |
| F04-T14 | Given PDF 且 PyMuPDF 提取质量不达标（mock/桩）When 索引 | Then 降级 Docling；job=succeeded；`parse_route=docling`；节/chunk 非空（样本为可解析 Office/PDF 替身） | unit |
| F04-T15 | Given `.docx` publish When 索引 | Then 不经 PyMuPDF；`parse_route=docling`（或 Docling mock）；job=succeeded | unit |
