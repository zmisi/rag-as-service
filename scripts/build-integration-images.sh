#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

tag="${1:-itest-$(date +%Y%m%d-%H%M)}"
platform="${PLATFORM:-linux/amd64}"
output_dir="${OUTPUT_DIR:-$repo_root/dist}"
pip_index_url="${PIP_INDEX_URL:-https://pypi.org/simple}"
pip_trusted_host="${PIP_TRUSTED_HOST:-}"
apex_host="${APEX_HOST:-lxzxai.com}"

backend_image="rag-as-service-backend:${tag}"
web_image="rag-as-service-web:${tag}"
db_image="rag-as-service-db:${tag}"
nginx_image="nginx:1.28-alpine"
archive="$output_dir/rag-as-service-${tag}-linux-amd64.tar.gz"

mkdir -p "$output_dir"
docker buildx inspect --bootstrap >/dev/null

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required to export apps/api/uv.lock" >&2
  exit 1
fi
uv lock --project "$repo_root/apps/api" --check
uv export \
  --project "$repo_root/apps/api" \
  --frozen \
  --no-dev \
  --no-emit-project \
  --no-hashes \
  --output-file "$repo_root/apps/api/requirements.lock" \
  >/dev/null

docker buildx build \
  --platform "$platform" \
  --load \
  --build-arg "PIP_INDEX_URL=$pip_index_url" \
  --build-arg "PIP_TRUSTED_HOST=$pip_trusted_host" \
  -t "$backend_image" \
  "$repo_root/apps/api"

docker buildx build \
  --platform "$platform" \
  --load \
  --build-arg "APEX_HOST=$apex_host" \
  -t "$web_image" \
  "$repo_root/apps/web"

docker buildx build \
  --platform "$platform" \
  --load \
  --file "$repo_root/deploy/Dockerfile.db" \
  -t "$db_image" \
  "$repo_root/deploy"

docker pull --platform "$platform" "$nginx_image"

for image in "$backend_image" "$web_image" "$db_image" "$nginx_image"; do
  architecture="$(
    docker image inspect \
      --platform "$platform" \
      "$image" \
      --format '{{.Os}}/{{.Architecture}}'
  )"
  if [[ "$architecture" != "$platform" ]]; then
    echo "unexpected architecture for $image: $architecture (expected $platform)" >&2
    exit 1
  fi
done

docker save "$backend_image" "$web_image" "$db_image" "$nginx_image" \
  | gzip >"$archive"
(
  cd "$output_dir"
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$(basename "$archive")" >"$(basename "$archive").sha256"
  else
    sha256sum "$(basename "$archive")" >"$(basename "$archive").sha256"
  fi
)

printf 'IMAGE_TAG=%s\n' "$tag"
printf 'Archive: %s\n' "$archive"
printf 'Checksum: %s\n' "$archive.sha256"
