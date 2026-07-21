"""Indexing package — F04 seam (search)."""

from rag_api.indexing.search import (
    ChunkHit,
    EmptyKnowledgeSearcher,
    FakeKnowledgeSearcher,
    KnowledgeSearcher,
)

__all__ = [
    "ChunkHit",
    "EmptyKnowledgeSearcher",
    "FakeKnowledgeSearcher",
    "KnowledgeSearcher",
]
