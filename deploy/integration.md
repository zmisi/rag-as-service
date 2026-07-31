# Linux 集成测试环境部署

本文用于在 arm64 macOS 构建 `linux/amd64` 镜像，并在无镜像仓库的 x86 Linux
服务器上导入和运行。集成环境使用固定镜像标签，不在服务器上构建镜像。

## 1. 本机构建镜像包

确认 Docker Desktop 与 `uv` 已安装。脚本会从已提交的 `apps/api/uv.lock`
导出 `requirements.lock`，然后在仓库根目录执行：

```bash
TAG="itest-$(date +%Y%m%d-%H%M)"
./scripts/build-integration-images.sh "$TAG"
```

使用自定义主域名时，构建 Web 镜像与部署环境必须使用相同的 `APEX_HOST`：

```bash
APEX_HOST=lxzai.dev.com ./scripts/build-integration-images.sh "$TAG"
```

脚本会构建以下镜像并验证其架构为 `linux/amd64`：

- `rag-as-service-backend:$TAG`：供 `api` 与 `ingest-worker` 共用
- `rag-as-service-web:$TAG`
- `rag-as-service-db:$TAG`：基于 `pgvector/pgvector:pg16`
- `nginx:1.28-alpine`

输出位于 `dist/`：

```text
rag-as-service-$TAG-linux-amd64.tar.gz
rag-as-service-$TAG-linux-amd64.tar.gz.sha256
```

默认使用官方 PyPI。仅在可信镜像完整同步 `hatchling`、Docling 等依赖时覆盖：

```bash
PIP_INDEX_URL=https://your-mirror.example/simple \
PIP_TRUSTED_HOST=your-mirror.example \
./scripts/build-integration-images.sh "$TAG"
```

## 2. 上传部署文件

上传脚本使用 `sshpass`，macOS 可执行：

```bash
brew install hudochenkov/sshpass/sshpass

cp scripts/integration_env.conf.example scripts/integration_env.conf
chmod 600 scripts/integration_env.conf
```

编辑 `scripts/integration_env.conf`，填写 `SERVER=user@host` 与
`SERVER_PASSWORD`；该文件已被 Git 忽略，不得提交。然后执行：

```bash
./scripts/upload-integration-images.sh "$TAG"
```

脚本会先校验本地 SHA-256，再创建服务器目录并上传镜像包、校验文件、
`docker-compose.integration.yml`、`nginx.conf.template` 与环境变量示例。上传时逐个
文件显示完成百分比、已传输大小和实时速度；远端文件完整接收后才会替换正式文件。

## 3. 服务器导入镜像

```bash
cd /opt/rag-as-service
sha256sum -c "rag-as-service-$TAG-linux-amd64.tar.gz.sha256"
gzip -dc "rag-as-service-$TAG-linux-amd64.tar.gz" | docker load
```

确认镜像架构：

```bash
docker image inspect \
  "rag-as-service-backend:$TAG" \
  "rag-as-service-web:$TAG" \
  --format '{{index .RepoTags 0}} {{.Os}}/{{.Architecture}}'
```

应全部显示 `linux/amd64`。

## 4. 配置环境变量

```bash
cd /opt/rag-as-service
cp deploy/.env.integration.example deploy/.env.integration
chmod 600 deploy/.env.integration
```

至少替换以下内容：

- `IMAGE_TAG=$TAG`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`（密码需 URL 编码）
- `SECRET_KEY`：可用 `openssl rand -hex 32`
- `PROXY_SHARED_SECRET`：使用另一份随机值
- `QWEN_API_KEY`

纯 HTTP 集成验证使用 `COOKIE_SECURE=false`。配置 HTTPS 后必须改为
`COOKIE_SECURE=true`。

## 5. 启动与检查

```bash
docker compose \
  --env-file deploy/.env.integration \
  -f deploy/docker-compose.integration.yml \
  up -d --no-build

docker compose \
  --env-file deploy/.env.integration \
  -f deploy/docker-compose.integration.yml \
  ps
```

检查日志：

```bash
docker compose \
  --env-file deploy/.env.integration \
  -f deploy/docker-compose.integration.yml \
  logs --tail=200 api ingest-worker web nginx
```

检查入口：

```bash
curl -i -H 'Host: lxzxai.com' http://127.0.0.1/backend/api/health
curl -I -H 'Host: lxzxai.com' http://127.0.0.1/login
```

生产验收前，`lxzxai.com` 与 `*.lxzxai.com` 必须解析到服务器入口，并配置有效
TLS 证书。本地 hosts 模拟不算生产验收。

## 6. 更新与回滚

构建新标签并重复上传、导入后，修改 `deploy/.env.integration` 的 `IMAGE_TAG`：

```bash
docker compose \
  --env-file deploy/.env.integration \
  -f deploy/docker-compose.integration.yml \
  up -d --no-build
```

回滚时把 `IMAGE_TAG` 改回上一个已导入标签，再执行同一命令。数据库迁移可能不
向后兼容，回滚应用前必须核对 Alembic 迁移；涉及破坏性迁移时先恢复数据库备份。

持久化数据位于 Docker 命名卷：

- `rag-as-service-integration_pgdata`
- `rag-as-service-integration_api_storage`
- `rag-as-service-integration_hf_cache`

不要使用 `docker compose down -v`，否则会删除数据库、上传文件和模型缓存。
