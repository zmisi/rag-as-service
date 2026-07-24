FROM python:3.12-slim

WORKDIR /app

# libpq5: psycopg. libxcb1/libgl1/libglib*: Docling/OpenCV headless runtime
# (otherwise: "libxcb.so.1: cannot open shared object file").
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      libpq5 \
      libxcb1 \
      libx11-6 \
      libxext6 \
      libxrender1 \
      libglib2.0-0 \
      libgl1 \
      libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY prompts ./prompts
COPY src ./src

# Optional Docling: --build-arg INSTALL_DOCLING=1
# Network tips (CN / flaky PyPI):
#   --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
#   --build-arg PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
# Official PyPI: leave PIP_INDEX_URL empty.
ARG INSTALL_DOCLING=0
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

ENV PIP_DEFAULT_TIMEOUT=1000 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_RETRIES=10

# Install with retries. Docling path:
# 1) base app from PyPI/mirror
# 2) torch/torchvision from pytorch.org with --no-deps (their CPU index often
#    serves dependency wheels whose hashes disagree with pip's expectations)
# 3) torch deps + docling from the mirror; pin torch so pip won't replace it
# 4) re-assert CPU torch wheels last
RUN set -eux; \
    PIP_OPTS="--no-cache-dir --default-timeout=1000 --retries 10"; \
    if [ -n "$PIP_INDEX_URL" ]; then \
      PIP_OPTS="$PIP_OPTS -i $PIP_INDEX_URL"; \
      if [ -n "$PIP_TRUSTED_HOST" ]; then \
        PIP_OPTS="$PIP_OPTS --trusted-host $PIP_TRUSTED_HOST"; \
      fi; \
    fi; \
    pip_retry() { \
      n=1; \
      while [ "$n" -le 5 ]; do \
        echo "pip attempt $n/5: $*"; \
        # shellcheck disable=SC2086
        pip install $PIP_OPTS "$@" && return 0; \
        echo "pip failed (attempt $n); sleeping before retry..."; \
        n=$((n + 1)); \
        sleep $((n * 5)); \
      done; \
      return 1; \
    }; \
    if [ "$INSTALL_DOCLING" = "1" ]; then \
      pip_retry -e .; \
      pip install --no-cache-dir --default-timeout=1000 --retries 10 \
        --index-url https://download.pytorch.org/whl/cpu \
        --no-deps \
        torch torchvision; \
      # Minimal runtime deps for the CPU wheels (from mirror / PyPI, not pytorch index).
      pip_retry typing-extensions sympy networkx jinja2 markupsafe mpmath pillow numpy; \
      pip_retry "docling>=2.0.0"; \
      pip install --no-cache-dir --default-timeout=1000 --retries 10 \
        --force-reinstall --no-deps \
        --index-url https://download.pytorch.org/whl/cpu \
        torch torchvision; \
    else \
      pip_retry -e .; \
    fi

EXPOSE 8000

CMD ["uvicorn", "rag_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
