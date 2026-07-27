# Bruno：F11 租户对外 API

集合目录：本文件夹。用 [Bruno](https://www.usebruno.com/) **Open Collection** 打开。

## 准备

1. API 已起：`uvicorn rag_api.main:app --reload --host 0.0.0.0 --port 8000`（`apps/api`）
2. 已 `alembic upgrade head`
3. Bruno：**Open Collection** 必须选本目录（含 `bruno.json` 的那一层），不要只开上级 `bruno/`
4. 顶部环境若仍是 **No Environment**（不要 Import `bruno.json`，会报 `missing or invalid variables array`）：
   - **推荐**：环境下拉 → **+ Create** → 名称 `local` → 按下方表格加变量 → Save
   - 或 **Import** → 选 `environments/local.env.json`（含 `variables` 数组）
5. 选中 **local**，改 `tenantSubdomain` / `email` / `password` 为真实值后保存
6. 直连 `127.0.0.1:8000` 即可（不必走 Next `/backend`）

### 若用 + Create 手建变量

| Name | 示例值 |
|------|--------|
| `baseUrl` | `http://127.0.0.1:8000` |
| `apexHost` | `lxzxai.com` |
| `tenantSubdomain` | 你的子域 |
| `email` | 你的邮箱 |
| `password` | 你的密码 |
| `sessionToken` | （留空，01 Login 会写） |
| `apiKeySecret` | （留空，02 Create 会写） |
| `apiKeyId` | （留空） |
| `conversationId` | （留空） |

## 推荐顺序

| # | 请求 | 说明 |
|---|------|------|
| 01 | Login | 主站 Host 登录 → 写入 `sessionToken` |
| 02 | Create API Key | 租户 Host + cookie → 写入 `apiKeySecret` |
| 03 | List API Keys | 确认无完整 secret |
| 04 | Public Search | Bearer 检索 |
| 05 | Public Chat | Bearer 问答（需 QWen 或 stub） |
| 06 | Wrong Host | 换 Host 测 403（改成库里另一个租户） |
| 07 | Revoke | 吊销后再跑 04 → 401 |

## 限流（F11-T07）

Bruno 无内置压测：对 04 连续发 >60 次，或跑：

```bash
cd apps/api && source .venv/bin/activate && set -a && source ../../.env && set +a
pytest tests/integration/test_f11_tenant_public_api.py::test_f11_t07_rate_limited -v
```
