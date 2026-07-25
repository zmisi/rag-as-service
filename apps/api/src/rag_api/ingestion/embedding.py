"""Embedding clients for F04temp (local hashing + optional QWen)."""

from __future__ import annotations

import hashlib
import logging
import math
import struct
from typing import Protocol

import httpx

from rag_api.config import Settings, get_settings
from rag_api.indexing.constants import EMBEDDING_DIM, QWEN_EMBEDDING_MODEL
from rag_api.observability.agent_log import log_system_call

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class HashingEmbedder:
    """Deterministic local embedder for F04temp / tests (no network)."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self._dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_l2_normalize(self._one(t)) for t in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        tokens = (text or "").lower().split()
        if not tokens:
            tokens = ["__empty__"]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            # Spread token into several dims
            for i in range(0, min(len(digest), 32), 4):
                idx = struct.unpack_from(">I", digest, i)[0] % self._dim
                sign = 1.0 if digest[i] % 2 == 0 else -1.0
                vec[idx] += sign
            # Character n-grams for CJK (no spaces)
            for ch in text:
                if ch.isspace():
                    continue
                d = hashlib.md5(ch.encode("utf-8")).digest()
                idx = struct.unpack_from(">H", d, 0)[0] % self._dim
                vec[idx] += 1.0
        return vec


class QwenEmbedder:
    """DashScope OpenAI-compatible embeddings API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = httpx.Client(http2=False, timeout=60.0)

    def embed(self, texts: list[str]) -> list[list[float]]:
        api_key = (self._settings.qwen_api_key or "").strip()
        base_url = (self._settings.qwen_base_url or "").strip().rstrip("/")
        if not api_key or not base_url:
            raise RuntimeError("QWen embedding requires QWEN_API_KEY / QWEN_BASE_URL")
        url = f"{base_url}/embeddings"
        model = (
            getattr(self._settings, "qwen_embedding_model", "") or QWEN_EMBEDDING_MODEL
        ).strip()
        log_system_call(
            "dashscope",
            "embeddings",
            model=model,
            url=url,
            input_count=len(texts),
            dimensions=EMBEDDING_DIM,
        )
        resp = self._client.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "input": texts,
                # Pin dim to match pgvector column / EMBEDDING_DIM.
                "dimensions": EMBEDDING_DIM,
            },
        )
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get("data") or []
        # API may return unsorted; sort by index
        data = sorted(data, key=lambda row: int(row.get("index", 0)))
        vectors = [list(map(float, row["embedding"])) for row in data]
        if len(vectors) != len(texts):
            raise RuntimeError(
                f"Embedding count mismatch: got {len(vectors)} for {len(texts)} texts"
            )
        for v in vectors:
            if len(v) != EMBEDDING_DIM:
                raise RuntimeError(
                    f"Unexpected embedding dim {len(v)}; expected {EMBEDDING_DIM}"
                )
        log_system_call(
            "dashscope",
            "embeddings.ok",
            model=model,
            vectors=len(vectors),
            dim=EMBEDDING_DIM,
        )
        return [_l2_normalize(v) for v in vectors]


def get_embedder(settings: Settings | None = None) -> Embedder:
    """Prefer QWen when explicitly enabled; otherwise hashing (F04temp local e2e)."""
    settings = settings or get_settings()
    if (settings.qwen_api_key or "").strip() and settings.qwen_embedding_enabled:
        logger.info("Using QwenEmbedder")
        return QwenEmbedder(settings)
    logger.info("Using HashingEmbedder (F04temp)")
    return HashingEmbedder()
