"""FastAPI dependencies for F06 Agent (LLM + knowledge search)."""

from __future__ import annotations

from functools import lru_cache

from rag_api.clients.llm import DevStubLlmClient, LlmClient, QwenClient
from rag_api.config import get_settings
from rag_api.indexing.search import EmptyKnowledgeSearcher, KnowledgeSearcher


@lru_cache
def _default_searcher() -> EmptyKnowledgeSearcher:
    return EmptyKnowledgeSearcher()


def get_knowledge_searcher() -> KnowledgeSearcher:
    """Production wires F04 search here; default empty until F04 is present."""
    return _default_searcher()


def get_llm_client() -> LlmClient:
    settings = get_settings()
    if settings.qwen_api_key:
        return QwenClient(settings)
    if settings.auth_stub_enabled:
        return DevStubLlmClient()
    return QwenClient(settings)
