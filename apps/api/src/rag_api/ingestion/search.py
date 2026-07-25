"""Chunk search types and KnowledgeSearcher protocol (F04)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from rag_api.indexing.embedding import Embedder, get_embedder
from rag_api.observability.agent_log import log_system_call, snip

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChunkHit:
    chunk_id: str
    document_id: str
    content: str  # section full text (F04 retrieval contract)
    score: float = 0.0
    section_id: str = ""
    path: str = ""


class KnowledgeSearcher(Protocol):
    def search(
        self,
        tenant_id: UUID,
        query: str,
        top_k: int = 5,
    ) -> list[ChunkHit]:
        """Return published ready latest section hits for tenant_id only."""
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
            score = 1.0 if q in text_l else (
                0.5 if any(t in text_l for t in q.split()) else 0.0
            )
            if score > 0:
                scored.append((score, hit))
        scored.sort(key=lambda x: x[0], reverse=True)
        # Deduplicate by section_id when present
        out: list[ChunkHit] = []
        seen: set[str] = set()
        for _, hit in scored:
            key = hit.section_id or hit.chunk_id
            if key in seen:
                continue
            seen.add(key)
            out.append(hit)
            if len(out) >= top_k:
                break
        return out


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


def dedupe_hits_by_section(hits: list[ChunkHit], top_k: int) -> list[ChunkHit]:
    """Keep highest-scoring hit per section_id (stable by input order of score)."""
    out: list[ChunkHit] = []
    seen: set[str] = set()
    for hit in hits:
        key = hit.section_id or hit.chunk_id
        if key in seen:
            continue
        seen.add(key)
        out.append(hit)
        if len(out) >= top_k:
            break
    return out


class PgKnowledgeSearcher:
    """pgvector cosine search over latest leaves; return section full text + path."""

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
        # Fetch extra leaves so section dedupe can still fill top_k
        fetch_k = max(top_k * 5, top_k)
        db: Session = self._session_factory()
        try:
            rows = db.execute(
                text(
                    """
                    SELECT
                      c.chunk_id::text AS chunk_id,
                      c.doc_id::text AS document_id,
                      c.section_id::text AS section_id,
                      s.path AS path,
                      s.content AS content,
                      (1 - (c.embedding <=> CAST(:qvec AS vector))) AS score
                    FROM rag_service.document_chunks c
                    INNER JOIN rag_service.document_sections s
                      ON s.id = c.section_id
                     AND s.tenant_id = c.tenant_id
                     AND s.is_latest = true
                    INNER JOIN rag_service.documents d
                      ON d.doc_id = c.doc_id
                     AND d.tenant_id = c.tenant_id
                    WHERE c.tenant_id = CAST(:tenant_id AS uuid)
                      AND c.is_latest = true
                      AND d.publish_status = 'published'
                      AND d.index_status = 'ready'
                      AND d.deleted_at IS NULL
                    ORDER BY c.embedding <=> CAST(:qvec AS vector)
                    LIMIT :fetch_k
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "qvec": lit,
                    "fetch_k": fetch_k,
                },
            ).mappings().all()
            raw_hits = [
                ChunkHit(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    content=row["content"],
                    score=float(row["score"] or 0.0),
                    section_id=row["section_id"] or "",
                    path=row["path"] or "",
                )
                for row in rows
            ]
            hits = dedupe_hits_by_section(raw_hits, top_k)
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
