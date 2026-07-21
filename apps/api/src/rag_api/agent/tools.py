"""Agent tools: whitelist + search_knowledge with tenant_id locked."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from rag_api.agent.constants import TOOL_SEARCH_KNOWLEDGE, TOOL_WHITELIST, TOP_K
from rag_api.agent.context import format_chunks_as_untrusted
from rag_api.indexing.search import KnowledgeSearcher

logger = logging.getLogger("rag_api.timing")


SEARCH_KNOWLEDGE_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": TOOL_SEARCH_KNOWLEDGE,
        "description": "Search the current tenant knowledge base for relevant document chunks.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query derived from the user question",
                }
            },
            "required": ["query"],
        },
    },
}


def tool_definitions() -> list[dict[str, Any]]:
    return [SEARCH_KNOWLEDGE_SCHEMA]


@dataclass
class ToolExecutionResult:
    ok: bool
    tool_name: str
    payload: dict[str, Any]
    content_for_llm: str
    used_search: bool = False
    error: str | None = None


class ToolExecutor:
    """Harness-side tool runner; tenant_id is closed over, never from model args."""

    def __init__(self, searcher: KnowledgeSearcher, tenant_id: UUID) -> None:
        self._searcher = searcher
        self._tenant_id = tenant_id

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        if name not in TOOL_WHITELIST:
            return ToolExecutionResult(
                ok=False,
                tool_name=name,
                payload={"error": "tool_not_allowed", "name": name},
                content_for_llm=f"工具 `{name}` 不在白名单中，已拒绝执行。",
                error=f"unknown_tool:{name}",
            )
        if name == TOOL_SEARCH_KNOWLEDGE:
            return self._search_knowledge(arguments)
        return ToolExecutionResult(
            ok=False,
            tool_name=name,
            payload={"error": "unhandled"},
            content_for_llm="工具执行失败。",
            error="unhandled",
        )

    def _search_knowledge(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        query = str(arguments.get("query") or "").strip()
        # Ignore any tenant_id the model might have hallucinated into args
        t0 = time.perf_counter()
        hits = self._searcher.search(self._tenant_id, query, top_k=TOP_K)
        search_ms = (time.perf_counter() - t0) * 1000.0
        chunks = [
            {
                "chunk_id": h.chunk_id,
                "document_id": h.document_id,
                "content": h.content,
                "score": h.score,
            }
            for h in hits
        ]
        logger.info(
            "timing search_knowledge search_ms=%.1f query_chars=%s hit_count=%s top_k=%s",
            search_ms,
            len(query),
            len(chunks),
            TOP_K,
        )
        payload = {
            "query": query,
            "chunks": chunks,
            "tenant_id": str(self._tenant_id),
            "timing_ms": {"search": round(search_ms, 1)},
        }
        return ToolExecutionResult(
            ok=True,
            tool_name=TOOL_SEARCH_KNOWLEDGE,
            payload=payload,
            content_for_llm=format_chunks_as_untrusted(chunks),
            used_search=True,
        )


def dump_payload(payload: dict[str, Any], limit: int = 4000) -> str:
    text = json.dumps(payload, ensure_ascii=False)
    if len(text) > limit:
        return text[:limit] + "…"
    return text
