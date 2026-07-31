#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config_file="$repo_root/scripts/integration_env.conf"

if [[ ! -f "$config_file" ]]; then
  echo "missing config: $config_file" >&2
  echo "copy scripts/integration_env.conf.example and fill in the server credentials" >&2
  exit 1
fi

# This file is local-only and gitignored. It must contain shell assignments.
# shellcheck source=/dev/null
source "$config_file"

tag="${TAG:-}"
remote_dir="${REMOTE_DIR:-/opt/rag-as-service}"
ssh_port="${SSH_PORT:-22}"

if [[ -z "$tag" ]]; then
  echo "usage: $0 <IMAGE_TAG>" >&2
  exit 1
fi
if [[ ! "$tag" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "invalid IMAGE_TAG: $tag" >&2
  exit 1
fi
if [[ -z "${SERVER:-}" ]]; then
  echo "SERVER is required in $config_file" >&2
  exit 1
fi
if [[ -z "${SERVER_PASSWORD:-}" ]]; then
  echo "SERVER_PASSWORD is required in $config_file" >&2
  exit 1
fi
if [[ ! "$SERVER" =~ ^[^[:space:]]+@[^[:space:]]+$ ]]; then
  echo "SERVER must use user@host format" >&2
  exit 1
fi
if [[ ! "$remote_dir" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
  echo "REMOTE_DIR must be an absolute path without spaces" >&2
  exit 1
fi
if [[ ! "$ssh_port" =~ ^[0-9]+$ ]]; then
  echo "SSH_PORT must be numeric" >&2
  exit 1
fi
if ! command -v sshpass >/dev/null 2>&1; then
  echo "sshpass is required (macOS: brew install hudochenkov/sshpass/sshpass)" >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to display upload progress" >&2
  exit 1
fi

archive="$repo_root/dist/rag-as-service-${tag}-linux-amd64.tar.gz"
checksum="${archive}.sha256"
deployment_files=(
  "$repo_root/deploy/docker-compose.integration.yml"
  "$repo_root/deploy/nginx.conf.template"
  "$repo_root/deploy/.env.integration.example"
)

for file in "$archive" "$checksum" "${deployment_files[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "missing upload artifact: $file" >&2
    exit 1
  fi
done

(
  cd "$(dirname "$archive")"
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 -c "$(basename "$checksum")"
  else
    sha256sum -c "$(basename "$checksum")"
  fi
)

export SSHPASS="$SERVER_PASSWORD"
trap 'unset SSHPASS' EXIT

ssh_options=(
  -p "$ssh_port"
  -o StrictHostKeyChecking=accept-new
)

sshpass -e ssh "${ssh_options[@]}" \
  "$SERVER" "mkdir -p '$remote_dir/deploy'"

upload_file() {
  local source_file="$1"
  local destination_dir="$2"
  local filename
  local file_size
  local destination

  filename="$(basename "$source_file")"
  file_size="$(wc -c < "$source_file" | tr -d '[:space:]')"
  destination="$destination_dir/$filename"

  python3 -u -c '
import os
import sys
import time

path = sys.argv[1]
total = os.path.getsize(path)
sent = 0
started = time.monotonic()
last_update = 0.0
output = sys.stdout.buffer

with open(path, "rb") as source:
    while chunk := source.read(1024 * 1024):
        output.write(chunk)
        output.flush()
        sent += len(chunk)
        now = time.monotonic()
        if now - last_update >= 0.2 or sent == total:
            last_update = now
            elapsed = max(now - started, 0.001)
            percent = 100.0 if total == 0 else sent * 100.0 / total
            print(
                f"\r上传 {os.path.basename(path)}: {percent:6.2f}%  "
                f"{sent / 1048576:.1f}/{total / 1048576:.1f} MiB  "
                f"{sent / elapsed / 1048576:.1f} MiB/s",
                end="",
                file=sys.stderr,
                flush=True,
            )

print(file=sys.stderr, flush=True)
' "$source_file" |
    sshpass -e ssh "${ssh_options[@]}" "$SERVER" \
      "cat > '$destination.part' && test \"\$(wc -c < '$destination.part')\" -eq '$file_size' && mv '$destination.part' '$destination'"
}

upload_file "$archive" "$remote_dir"
upload_file "$checksum" "$remote_dir"
for file in "${deployment_files[@]}"; do
  upload_file "$file" "$remote_dir/deploy"
done

printf 'Uploaded IMAGE_TAG=%s to %s:%s\n' "$tag" "$SERVER" "$remote_dir"
