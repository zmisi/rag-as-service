"""FastAPI dependencies for F06 Agent (LLM + knowledge search)."""

from __future__ import annotations

from functools import lru_cache

from rag_api.clients.llm import DevStubLlmClient, LlmClient, QwenClient
from rag_api.config import get_settings
from rag_api.db.session import get_session_factory
from rag_api.indexing.embedding import get_embedder
from rag_api.indexing.search import KnowledgeSearcher, PgKnowledgeSearcher


@lru_cache
def _default_searcher() -> PgKnowledgeSearcher:
    # F04temp: always wire pgvector search (hashing embedder when no QWen emb).
    return PgKnowledgeSearcher(get_session_factory(), embedder=get_embedder())


def get_knowledge_searcher() -> KnowledgeSearcher:
    return _default_searcher()


def get_llm_client() -> LlmClient:
    settings = get_settings()
    if settings.qwen_api_key:
        return QwenClient(settings)
    if settings.auth_stub_enabled:
        return DevStubLlmClient()
    return QwenClient(settings)
