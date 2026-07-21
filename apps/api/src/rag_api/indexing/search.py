"""Chunk search types and KnowledgeSearcher protocol (F04 seam)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


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
    """Production fallback until F04 search is wired; always returns []."""

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
            text = hit.content.lower()
            score = 1.0 if q in text else (0.5 if any(t in text for t in q.split()) else 0.0)
            if score > 0:
                scored.append((score, hit))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [h for _, h in scored[:top_k]]
