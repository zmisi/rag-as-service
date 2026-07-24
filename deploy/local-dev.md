# 本地多子域开发

Phase 1 注册/登录在主站 `lxzxai.com`；租户站在 `{subdomain}.lxzxai.com`。

## /etc/hosts（示例）

```text
127.0.0.1 lxzxai.com
127.0.0.1 acme.lxzxai.com
```

**重要**：注册时你选定的每个 `{subdomain}` 都要能解析到本机，否则注册成功跳转到 `{subdomain}.lxzxai.com` 会打到公网 DNS，出现 **502**。

注册 `ocp14` 后需追加：

```text
127.0.0.1 ocp14.lxzxai.com
```

### 通配子域（推荐，免每次改 hosts）

macOS 可用 [dnsmasq](https://formulae.brew.sh/formula/dnsmasq)：

```bash
brew install dnsmasq
echo "address=/.lxzxai.com/127.0.0.1" >> $(brew --prefix)/etc/dnsmasq.conf
sudo brew services start dnsmasq
sudo mkdir -p /etc/resolver
echo "nameserver 127.0.0.1" | sudo tee /etc/resolver/lxzxai.com
```

之后任意 `{subdomain}.lxzxai.com` 均指向本机。

访问时请带端口：**http://lxzxai.com:3000/register**（不要用无端口的 `http://lxzxai.com`，否则跳转 URL 不会改写 `:3000`）。

## Docker Compose

```bash
# 仓库根目录
cp deploy/.env.example .env
docker compose -f deploy/docker-compose.yml up --build

# 如果需要重建API镜像，可以运行下面命令
docker compose -f deploy/docker-compose.yml build \
  --build-arg INSTALL_DOCLING=1 \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  --build-arg PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
  api 

docker compose -f deploy/docker-compose.yml up -d --force-recreate api web index_worker 

# 查看详细日志
# 只看 API（索引 / parse_route / 报错最常用）
docker compose -f deploy/docker-compose.yml logs -f api

# API + Web
docker compose -f deploy/docker-compose.yml logs -f api web

# 全部服务
docker compose -f deploy/docker-compose.yml logs -f

```

服务：

| 服务 | 说明 | 端口 |
|------|------|------|
| `db` | PostgreSQL 16 + pgvector | 5432 |
| `api` | FastAPI；`AUTO_MIGRATE=true` 自动迁移 | 8000 |
| `web` | Next.js；`/backend/*` → `api:8000` | 3000 |

访问：

- 注册：http://lxzxai.com:3000/register
- 登录：http://lxzxai.com:3000/login
- 文档管理：http://{subdomain}.lxzxai.com:3000/admin（上传 → 提交审核 → 发布）

登录成功后跳转到 `https://{subdomain}.lxzxai.com/`（聊天入口）；注册成功后跳转到 `/admin`。

F02 起默认使用 cookie 会话鉴权；**无需**开启 `AUTH_STUB_ENABLED`（该开关仅作本地 UI 过渡 fallback）。

**聊天 Agent（F06）**：根目录 `.env` 须配置 `QWEN_API_KEY`（及可选 `QWEN_BASE_URL` / `QWEN_MODEL`）。`api` 服务通过 `env_file: ../.env` 注入（compose 文件在 `deploy/` 下时，默认**不会**自动读仓库根 `.env` 做 `${VAR}` 替换）。改完后：

```bash
docker compose -f deploy/docker-compose.yml up -d --force-recreate api
docker compose -f deploy/docker-compose.yml exec api env | grep QWEN_API_KEY
# 应看到非空 Key（不要把输出贴到聊天里）
```

API 容器内 `DATABASE_URL` 指向 `db:5432`（compose 自动注入，无需手改）。

开发时挂载了源码目录，改 `apps/api/src` / `apps/web` 可热更新。另有命名卷 `api_storage` 挂到 `/app/var/storage`，用于保留已上传的文档源文件；重建 `api` 镜像/容器后文件不会丢。

### 常用：启停 / 迁移后重建

热重载**不会**重新跑 Alembic。有新迁移（如 F07）或 API 行为异常时，重建 `api`；`web` 若已退出需单独拉起。

```bash
# 查看状态（web 可能是 Exited）
docker compose -f deploy/docker-compose.yml ps -a

# 重建 api（触发 AUTO_MIGRATE）
docker compose -f deploy/docker-compose.yml up -d --force-recreate api

# 仅启动已停止的 web（不要写 start 当服务名）
docker compose -f deploy/docker-compose.yml up -d web

# 一次重建 api + 启动 web
docker compose -f deploy/docker-compose.yml up -d --force-recreate api web index-worker

# 手动调用 run-pending（仅当前租户；生产由 index-worker 消费）
curl -X POST 'http://127.0.0.1:8000/v1/documents/index/run-pending' \
  -H 'Host: opc15.lxzxai.com' \
  -H 'Content-Type: application/json' \
  -b 'pb_session=eBFP3lHKDLheVtMOyPglWJUL36vNXJQhPXy17ktgkNw'
```

可选边缘入口（Caddy，可信 Host / XFH）：

```bash
docker compose -f deploy/docker-compose.yml --profile caddy up -d
# 访问 http://lxzxai.com:8080 （/backend → api，其余 → web）
```

确认迁移已到最新：

```bash
docker compose -f deploy/docker-compose.yml logs api --tail 40
```

日志中应有 `head=20260722_f07_data_model`（或当前最新 revision）以及 `Application startup complete`。

错误示例：`up -d start web` 会报 `no such service: start`——`start` 不是服务名，正确是 `up -d web`。

## 原生进程（不用 Docker）

```bash
# 终端 1 — API（与 Web 共用 PROXY_SHARED_SECRET）
cd apps/api && source .venv/bin/activate
export PROXY_SHARED_SECRET=local-dev-proxy-secret
uvicorn rag_api.main:app --reload --port 8000

# 终端 2 — Index worker
cd apps/api && source .venv/bin/activate
rag-index-worker

# 终端 3 — Web
cd apps/web && \
  PROXY_SHARED_SECRET=local-dev-proxy-secret \
  API_BACKEND_URL=http://localhost:8000 \
  npm run dev
```

访问：http://lxzxai.com:3000/login 或 `/register`（`localhost` 仅可看 UI；鉴权走 `/backend` BFF，由服务端注入 `X-Forwarded-Host`）。

**Docker 含 PDF/Office 解析**（安装 CPU 版 torch，避免拉 CUDA 大包超时）：

```bash
# 建议：.env 里保留清华源（deploy/.env.example 已写）；需要 Docling 时：
INSTALL_DOCLING=1 docker compose -f deploy/docker-compose.yml build api
docker compose -f deploy/docker-compose.yml up
```

或一次性：

```bash
docker compose -f deploy/docker-compose.yml build \
  --build-arg INSTALL_DOCLING=1 \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  --build-arg PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
  api
```

构建易失败（超时 / hash mismatch）时：

1. 确认用了国内 PyPI 镜像（默认清华）；不要用 `--extra-index-url` 混源装 Docling
2. 清掉坏缓存后重试：`docker builder prune -f` 再 `build --no-cache api`
3. 仅文字层 PDF 可先 `INSTALL_DOCLING=0`（PyMuPDF 足够），少下一大包
4. 若索引报 `libxcb.so.1: cannot open shared object file`：确认用的是含系统库的新 Dockerfile 后 **重建 api 镜像**（`INSTALL_DOCLING=1 ... build api`）

说明：

- `.pdf`：**PyMuPDF fast path**（默认依赖，轻量）→ 质量门限不达标时再 **Docling fallback**
- `.docx` / `.xlsx` / `.pptx`：轻量库（`python-docx` / `openpyxl` / `python-pptx`），**不用 Docling**
- 首次走 Docling（结构化 PDF）时会从 Hugging Face 拉模型，发布接口可能较慢；模型缓存后会明显加快
- `INDEX_SYNC_ON_PUBLISH=true` 时发布会同步跑完索引（本地捷径）；Compose 默认 `false`，由 `index-worker`（`rag-index-worker`）轮询消费 `index_job`（`FOR UPDATE SKIP LOCKED` + stuck reclaim）
- 浏览器**不要**自带 `X-Forwarded-Host`；由 Next `/backend` BFF 或 Caddy 注入，并带 `X-Rag-Proxy-Secret`

E2E：`E2E_ENABLED=1` + `DATABASE_URL` 后 `cd apps/web && npm run test:e2e`。

## F04 / F07 / F08 文档索引与数据模型（本地）

发布 `published` 文档后会写入 `index_job`；Compose 默认由 **`index-worker`** 异步消费（`INDEX_SYNC_ON_PUBLISH=false`）。文档行是**版本行**（`document_group_id` + int `version`）；检索门禁为 `publish_status=published` 且 `index_status=ready` 且 section/chunk `is_latest=true`。

| 能力 | 说明 |
|------|------|
| `.txt` / `.md` | 内置文本解析；上传侧扩展名 + 无 `\x00` 魔数抽检 |
| `.pdf` | **PyMuPDF → Docling** 双路由；头魔数 `%PDF`；质量阈值见 `PDF_FAST_*` |
| `.docx` / `.pptx` / `.xlsx` | 轻量库 → 内存 Markdown；ZIP + `word/`/`ppt/`/`xl/` 魔数；`parse_route=docx\|pptx\|xlsx` |
| 切块 | H1–H6 节树 + 节内 leaf（`CHUNK_TARGET_TOKENS` / `CHUNK_OVERLAP_TOKENS`） |
| Embedding | 默认 `HashingEmbedder`（本地无 DashScope）；生产可设 `QWEN_EMBEDDING_ENABLED=true`；审计字段写在 **documents** |
| PDF 路由 | **有骨架**（书签 TOC / 字号标题候选，或 `PDF_FORCE_STRUCTURE=true`）→ Docling 结构路径；**无骨架纯文字** → PyMuPDF；结构 PDF 需 `INSTALL_DOCLING=1` |
| 源文件持久化 | Compose 卷 `api_storage` → `/app/var/storage` |
| 同租户去重 | 相同 `content_sha256` 且已有 `ready` latest → 跳过 parse/embedding，**克隆** section/chunk 到本 `doc_id`（可检索） |

**迁移 / 重建索引：**

1. `AUTO_MIGRATE=true`（Compose 默认）会应用至 **`20260724_drop_sections_level_chk`**（含 F04/F07/F08 及去掉 `document_sections_level_chk`）。
2. **拉最新代码后须重建 `api`**（热重载不够）：见上文「常用：启停 / 迁移后重建」；若 `web` 为 Exited，再 `up -d web`。
3. 原生进程：`cd apps/api && uv run alembic upgrade head`。
4. **F08 为破坏性重命名**（`tenant_id`/`user_id`/`doc_id`/`chunk_id`，`subdomain`→`tenant_name`，`version`→`version_number` 等）。迁移失败时可重建 Postgres 卷后再 `upgrade head`。
5. F07 升级时会清空旧 `document_sections` / `document_chunks`（需 **reindex**）。
6. 对已 `published` 文档：重新走发布流，或确保有 pending `index_job` 后调用 `POST /v1/documents/index/run-pending`。
7. **节树改为 H1–H6 后**：已 `ready` 的文档仍是旧 H1/H2 切分；须重新 publish / 跑 index job 才会按 H1–H6 重建。

**集成测试：**

```bash
cd apps/api
DATABASE_URL=postgresql+psycopg://rag_app:rag_app@127.0.0.1:5432/lxzxai_rag \
  uv run pytest \
  tests/integration/test_f03_doc_admin.py \
  tests/integration/test_f04_doc_indexing.py \
  tests/integration/test_f07_doc_indexing_data_model.py -q
```

（Compose 默认库账号见 `deploy/.env.example`。）
