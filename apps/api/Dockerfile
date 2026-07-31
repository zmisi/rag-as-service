FROM python:3.12-slim AS builder

WORKDIR /build

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=
ARG DOCLING_VERSION=2.114.0
ARG TORCH_VERSION=2.13.0
ARG TORCHVISION_VERSION=0.28.0

ENV PIP_DEFAULT_TIMEOUT=1000 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_RETRIES=10 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

RUN python -m venv "${VIRTUAL_ENV}"

COPY pyproject.toml requirements.lock README.md ./
COPY src ./src

# Build and install the application as a wheel-backed, non-editable package.
# Keep CPU-only torch wheels even when Docling resolves its model dependencies.
RUN set -eux; \
    PIP_OPTS="--no-cache-dir --default-timeout=1000 --retries 10"; \
    if [ -n "$PIP_INDEX_URL" ]; then \
      PIP_OPTS="$PIP_OPTS --index-url $PIP_INDEX_URL"; \
      if [ -n "$PIP_TRUSTED_HOST" ]; then \
        PIP_OPTS="$PIP_OPTS --trusted-host $PIP_TRUSTED_HOST"; \
      fi; \
    fi; \
    pip_retry() { \
      n=1; \
      while [ "$n" -le 5 ]; do \
        echo "pip attempt $n/5: $*"; \
        # shellcheck disable=SC2086
        if pip install $PIP_OPTS "$@"; then \
          return 0; \
        fi; \
        if [ "$n" -eq 5 ]; then \
          return 1; \
        fi; \
        n=$((n + 1)); \
        sleep $((n * 5)); \
      done; \
    }; \
    pip_retry --requirement requirements.lock; \
    pip_retry --no-deps .; \
    pip_retry \
      --index-url https://download.pytorch.org/whl/cpu \
      --no-deps \
      "torch==${TORCH_VERSION}" \
      "torchvision==${TORCHVISION_VERSION}"; \
    pip_retry typing-extensions sympy networkx jinja2 markupsafe mpmath pillow numpy; \
    pip_retry "docling==${DOCLING_VERSION}"; \
    pip_retry \
      --force-reinstall \
      --no-deps \
      --index-url https://download.pytorch.org/whl/cpu \
      "torch==${TORCH_VERSION}" \
      "torchvision==${TORCHVISION_VERSION}"


FROM python:3.12-slim AS runtime

WORKDIR /app

# libpq5: psycopg. libxcb1/libgl1/libglib*: Docling/OpenCV headless runtime.
RUN set -eux; \
    n=1; \
    while true; do \
      if apt-get -o Acquire::Retries=5 update \
        && apt-get -o Acquire::Retries=5 install -y --no-install-recommends \
          libpq5 \
          libxcb1 \
          libx11-6 \
          libxext6 \
          libxrender1 \
          libglib2.0-0 \
          libgl1 \
          libgomp1; then \
        break; \
      fi; \
      if [ "$n" -eq 5 ]; then \
        exit 1; \
      fi; \
      n=$((n + 1)); \
      rm -rf /var/lib/apt/lists/*; \
      sleep $((n * 5)); \
    done; \
    rm -rf /var/lib/apt/lists/*; \
    groupadd --gid 10001 rag; \
    useradd --uid 10001 --gid rag --create-home --shell /usr/sbin/nologin rag

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RAG_API_ROOT=/app

COPY --from=builder /opt/venv /opt/venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY prompts ./prompts

RUN mkdir -p /app/var/storage /app/var/hf-cache \
    && chown -R rag:rag /app

USER rag

EXPOSE 8000

CMD ["uvicorn", "rag_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
