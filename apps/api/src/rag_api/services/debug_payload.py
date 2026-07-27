"""P3-F04: build Agent debug payload from LoopResult (no secrets)."""

from __future__ import annotations

import json
import re
from typing import Any

from rag_api.agent.constants import LLM_TIMEOUT_S, TOOL_SEARCH_KNOWLEDGE
from rag_api.agent.context import assemble_messages
from rag_api.agent.loop import LoopResult
from rag_api.api.schemas.debug import AgentDebugPayload, DebugLlmCall, DebugSearchHit
from rag_api.config import Settings, get_settings
from rag_api.db.models import Message

_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|authorization|bearer|secret|password|token)",
    re.IGNORECASE,
)


def _secret_values(settings: Settings) -> list[str]:
    """Collect configured secret strings that must never appear in debug output."""
    values: list[str] = []
    for raw in (
        settings.qwen_api_key,
        settings.secret_key,
        settings.proxy_shared_secret,
    ):
        if raw and len(raw) >= 8:
            values.append(raw)
    return values


def scrub_secrets(value: Any, *, settings: Settings | None = None) -> Any:
    """Recursively redact known secrets and sensitive-looking keys from debug trees."""
    cfg = settings or get_settings()
    secrets = _secret_values(cfg)

    def _scrub(node: Any) -> Any:
        if isinstance(node, dict):
            out: dict[str, Any] = {}
            for key, val in node.items():
                if _SECRET_KEY_RE.search(str(key)):
                    out[key] = "[REDACTED]"
                else:
                    out[key] = _scrub(val)
            return out
        if isinstance(node, list):
            return [_scrub(item) for item in node]
        if isinstance(node, str):
            text = node
            for secret in secrets:
                if secret in text:
                    text = text.replace(secret, "[REDACTED]")
            return text
        return node

    return _scrub(value)


def build_agent_debug_payload(
    *,
    history: list[Message],
    user_content: str,
    loop: LoopResult,
    settings: Settings | None = None,
) -> AgentDebugPayload:
    """Derive debug panel fields from loop steps and the same assemble_messages path."""
    cfg = settings or get_settings()
    history_view = [
        {"role": m.role, "content": m.content}
        for m in history
        if m.role in ("user", "assistant", "system", "summary", "tool")
    ]
    context_messages = assemble_messages(
        history=history,
        user_content=user_content,
        tool_messages=None,
    )

    top_k_hits: list[DebugSearchHit] = []
    seen_chunks: set[str] = set()
    llm_calls: list[DebugLlmCall] = []
    llm_step_index = 0

    for step in loop.steps:
        if step.step_type == "tool_result" and step.tool_name == TOOL_SEARCH_KNOWLEDGE:
            chunks = (step.payload or {}).get("chunks") or []
            for chunk in chunks:
                if not isinstance(chunk, dict):
                    continue
                chunk_id = str(chunk.get("chunk_id") or chunk.get("id") or "")
                if chunk_id and chunk_id in seen_chunks:
                    continue
                if chunk_id:
                    seen_chunks.add(chunk_id)
                top_k_hits.append(
                    DebugSearchHit(
                        document_id=str(chunk.get("document_id") or ""),
                        chunk_id=chunk_id,
                        section_id=str(chunk.get("section_id") or ""),
                        path=str(chunk.get("path") or ""),
                        content=str(chunk.get("content") or ""),
                        score=float(chunk.get("score") or 0.0),
                    )
                )
        if step.step_type == "llm":
            llm_step_index += 1
            payload = step.payload or {}
            tool_calls = payload.get("tool_calls") or []
            request_summary = {
                "model": payload.get("model") or cfg.qwen_model,
                "timeout_s": LLM_TIMEOUT_S,
                "step": llm_step_index,
                "tool_calls": [
                    {
                        "id": tc.get("id"),
                        "name": tc.get("name"),
                        "arguments": tc.get("arguments"),
                    }
                    for tc in tool_calls
                    if isinstance(tc, dict)
                ],
            }
            response_summary = {
                "content": payload.get("content"),
                "finish_reason": payload.get("finish_reason"),
                "usage": payload.get("usage") or {},
                "tool_calls": request_summary["tool_calls"],
            }
            llm_calls.append(
                DebugLlmCall(
                    step=llm_step_index,
                    request_summary=request_summary,
                    response_summary=response_summary,
                )
            )

    raw = AgentDebugPayload(
        context_messages=context_messages,
        top_k_hits=top_k_hits,
        history=history_view,
        llm_calls=llm_calls,
    )
    scrubbed = scrub_secrets(raw.model_dump(), settings=cfg)
    return AgentDebugPayload.model_validate(scrubbed)


def assert_no_secrets_in_payload(payload: Any, *, settings: Settings | None = None) -> None:
    """Raise AssertionError if known secrets appear in serialized debug payload (tests)."""
    cfg = settings or get_settings()
    dumped = json.dumps(payload, ensure_ascii=False, default=str)
    for secret in _secret_values(cfg):
        if secret in dumped:
            raise AssertionError("debug payload contains a configured secret")
