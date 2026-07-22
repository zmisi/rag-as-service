"""Chunk search types and KnowledgeSearcher protocol (F04 seam)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from rag_api.indexing.embedding import Embedder, HashingEmbedder, get_embedder
from rag_api.observability.agent_log import log_system_call, snip

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChunkHit:
    chunk_id: str
    document_id: str
    content: str
    score: float = 0.0


class KnowledgeSearcher(Protocol):
    def search(
        self,
        tenant_id: UUID,
        query: str,
        top_k: int = 5,
    ) -> list[ChunkHit]:
        """Return published active chunks for tenant_id only."""
        ...


class EmptyKnowledgeSearcher:
    """Fallback that always returns []."""

    def search(
        self,
        tenant_id: UUID,
        query: str,
        top_k: int = 5,
    ) -> list[ChunkHit]:
        return []


class FakeKnowledgeSearcher:
    """In-memory corpora keyed by tenant_id for tests."""

    def __init__(self) -> None:
        self._corpus: dict[UUID, list[ChunkHit]] = {}

    def seed(self, tenant_id: UUID, chunks: list[ChunkHit]) -> None:
        self._corpus[tenant_id] = list(chunks)

    def search(
        self,
        tenant_id: UUID,
        query: str,
        top_k: int = 5,
    ) -> list[ChunkHit]:
        chunks = self._corpus.get(tenant_id, [])
        q = query.strip().lower()
        if not q:
            return []
        scored: list[tuple[float, ChunkHit]] = []
        for hit in chunks:
            text_l = hit.content.lower()
            score = 1.0 if q in text_l else (0.5 if any(t in text_l for t in q.split()) else 0.0)
            if score > 0:
                scored.append((score, hit))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [h for _, h in scored[:top_k]]


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


class PgKnowledgeSearcher:
    """pgvector cosine search over active chunks of published, non-deleted docs."""

    def __init__(
        self,
        session_factory,
        *,
        embedder: Embedder | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._embedder = embedder or get_embedder()

    def search(
        self,
        tenant_id: UUID,
        query: str,
        top_k: int = 5,
    ) -> list[ChunkHit]:
        q = (query or "").strip()
        if not q or top_k <= 0:
            return []
        embedder_name = type(self._embedder).__name__
        log_system_call(
            "embedder",
            "embed_query",
            embedder=embedder_name,
            query=snip(q, 160),
            query_chars=len(q),
        )
        vector = self._embedder.embed([q])[0]
        lit = _vector_literal(vector)
        db: Session = self._session_factory()
        try:
            rows = db.execute(
                text(
                    """
                    SELECT
                      c.id::text AS chunk_id,
                      c.document_id::text AS document_id,
                      c.content AS content,
                      (1 - (c.embedding <=> CAST(:qvec AS vector))) AS score
                    FROM rag_service.document_chunks c
                    INNER JOIN rag_service.documents d
                      ON d.id = c.document_id
                     AND d.tenant_id = c.tenant_id
                    WHERE c.tenant_id = CAST(:tenant_id AS uuid)
                      AND c.is_active = true
                      AND d.status = 'published'
                      AND d.deleted_at IS NULL
                    ORDER BY c.embedding <=> CAST(:qvec AS vector)
                    LIMIT :top_k
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "qvec": lit,
                    "top_k": top_k,
                },
            ).mappings().all()
            hits = [
                ChunkHit(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    content=row["content"],
                    score=float(row["score"] or 0.0),
                )
                for row in rows
            ]
            logger.info(
                "timing search_pg tenant_id=%s query_chars=%s hit_count=%s top_k=%s",
                tenant_id,
                len(q),
                len(hits),
                top_k,
            )
            log_system_call(
                "pgvector",
                "cosine_search",
                tenant_id=str(tenant_id),
                query=snip(q, 160),
                hit_count=len(hits),
                top_k=top_k,
                top_score=f"{hits[0].score:.4f}" if hits else None,
            )
            return hits
        finally:
            db.close()
