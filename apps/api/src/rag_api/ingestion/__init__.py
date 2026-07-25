"""Ingestion package — F04 (parse / sections / chunk / embed / search)."""

from rag_api.ingestion.search import (
    ChunkHit,
    EmptyKnowledgeSearcher,
    FakeKnowledgeSearcher,
    KnowledgeSearcher,
    PgKnowledgeSearcher,
)

__all__ = [
    "ChunkHit",
    "EmptyKnowledgeSearcher",
    "FakeKnowledgeSearcher",
    "KnowledgeSearcher",
    "PgKnowledgeSearcher",
]
