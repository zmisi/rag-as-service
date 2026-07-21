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

登录成功后跳转到 `https://{subdomain}.lxzxai.com/`（聊天入口）；注册成功后跳转到 `/admin`。

F02 起默认使用 cookie 会话鉴权；**无需**开启 `AUTH_STUB_ENABLED`（该开关仅作本地 UI 过渡 fallback）。

API 容器内 `DATABASE_URL` 指向 `db:5432`（compose 自动注入，无需手改）。

开发时挂载了源码目录，改 `apps/api/src` / `apps/web` 可热更新。

## 原生进程（不用 Docker）

```bash
# 终端 1 — API
cd apps/api && source .venv/bin/activate
uvicorn rag_api.main:app --reload --port 8000

# 终端 2 — Web
cd apps/web && npm run dev
```

访问：http://lxzxai.com:3000/login 或 `/register`（`localhost` 仅可看 UI；鉴权 API 需 `Host: lxzxai.com` 或 `{subdomain}.lxzxai.com`）。

E2E：`E2E_ENABLED=1` + `DATABASE_URL` 后 `cd apps/web && npm run test:e2e`。
