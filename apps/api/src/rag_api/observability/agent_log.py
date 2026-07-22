"""Structured debug logging helpers for Agent / LLM / cross-system calls."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("rag_api.agent_trace")

# Keep logs useful without dumping entire corpora into the terminal.
_DEFAULT_SNIP = 400
_MAX_MSG_SNIP = 600
_MAX_REPLY_SNIP = 1200


def snip(text: str | None, limit: int = _DEFAULT_SNIP) -> str:
    raw = (text or "").replace("\n", "\\n")
    if len(raw) <= limit:
        return raw
    return raw[:limit] + f"…(+{len(raw) - limit} chars)"


def role_counts(messages: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for m in messages:
        role = str(m.get("role") or "?")
        counts[role] = counts.get(role, 0) + 1
    return ",".join(f"{k}:{v}" for k, v in sorted(counts.items()))


def summarize_messages(messages: list[dict[str, Any]], *, limit_each: int = _MAX_MSG_SNIP) -> str:
    lines: list[str] = []
    for i, m in enumerate(messages):
        role = m.get("role")
        content = m.get("content")
        extra = ""
        if m.get("tool_calls"):
            names = []
            for tc in m["tool_calls"]:
                fn = (tc.get("function") or {}) if isinstance(tc, dict) else {}
                names.append(str(fn.get("name") or tc.get("name") or "?"))
            extra = f" tool_calls=[{','.join(names)}]"
        if m.get("tool_call_id"):
            extra += f" tool_call_id={m.get('tool_call_id')}"
        lines.append(f"  [{i}] role={role} chars={len(str(content or ''))}{extra} text={snip(str(content or ''), limit_each)}")
    return "\n".join(lines)


def dump_json(obj: Any, limit: int = 2000) -> str:
    try:
        text = json.dumps(obj, ensure_ascii=False, default=str)
    except TypeError:
        text = str(obj)
    if len(text) <= limit:
        return text
    return text[:limit] + f"…(+{len(text) - limit} chars)"


def log_llm_request(
    *,
    system: str,
    model: str,
    url: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
) -> None:
    tool_names = []
    for t in tools or []:
        fn = (t.get("function") or {}) if isinstance(t, dict) else {}
        tool_names.append(str(fn.get("name") or t.get("name") or "?"))
    logger.info(
        "llm.request system=%s model=%s url=%s msg_count=%s roles={%s} "
        "tool_defs=%s tools=%s approx_input_chars=%s",
        system,
        model,
        url,
        len(messages),
        role_counts(messages),
        len(tools or []),
        tool_names,
        sum(len(str(m.get("content") or "")) for m in messages),
    )
    logger.info("llm.request.messages\n%s", summarize_messages(messages))


def log_llm_response(
    *,
    system: str,
    model: str,
    http_ms: float,
    content: str | None,
    tool_calls: list[Any],
    usage: dict[str, Any] | None,
    finish_reason: str | None = None,
) -> None:
    tc_bits = []
    for tc in tool_calls:
        name = getattr(tc, "name", None) or (tc.get("name") if isinstance(tc, dict) else "?")
        args = getattr(tc, "arguments", None)
        if args is None and isinstance(tc, dict):
            args = tc.get("arguments")
        tc_bits.append(f"{name}({dump_json(args, 300)})")
    usage = usage or {}
    logger.info(
        "llm.response system=%s model=%s http_ms=%.1f finish_reason=%s "
        "prompt_tokens=%s completion_tokens=%s total_tokens=%s "
        "content_chars=%s tool_calls=%s content=%s",
        system,
        model,
        http_ms,
        finish_reason or "-",
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
        usage.get("total_tokens"),
        len(content or ""),
        len(tool_calls),
        snip(content, _MAX_REPLY_SNIP),
    )
    if tc_bits:
        logger.info("llm.response.tools %s", " | ".join(tc_bits))


def log_agent(event: str, **fields: Any) -> None:
    logger.info("agent.%s %s", event, " ".join(f"{k}={v}" for k, v in fields.items() if v is not None))


def log_system_call(system: str, action: str, **fields: Any) -> None:
    logger.info(
        "system.%s action=%s %s",
        system,
        action,
        " ".join(f"{k}={v}" for k, v in fields.items() if v is not None),
    )
