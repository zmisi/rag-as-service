"""LLM client protocol and QWen (DashScope-compatible) implementation."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from rag_api.agent.constants import LLM_TIMEOUT_S, NO_HIT_PHRASE, TOOL_SEARCH_KNOWLEDGE
from rag_api.config import Settings, get_settings

logger = logging.getLogger(__name__)
_QWEN_HTTP_CLIENT = httpx.Client(
    http2=False,
    timeout=LLM_TIMEOUT_S,
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LlmResult:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LlmTimeoutError(Exception):
    """Raised when the LLM call times out, fails, or is unreachable."""


class LlmClient(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LlmResult:
        ...


class ScriptedLlmClient:
    """Test double: returns a scripted sequence of LlmResult or exceptions."""

    def __init__(self, script: list[LlmResult | BaseException]) -> None:
        self._script = list(script)
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LlmResult:
        self.calls.append({"messages": messages, "tools": tools})
        if not self._script:
            return LlmResult(content="（脚本已耗尽）")
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def _sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """DashScope rejects null content; coerce to empty string when tool_calls present."""
    out: list[dict[str, Any]] = []
    for raw in messages:
        msg = dict(raw)
        if msg.get("content") is None:
            msg["content"] = ""
        out.append(msg)
    return out


class QwenClient:
    """OpenAI-compatible chat completions against DashScope / QWen."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LlmResult:
        api_key = (getattr(self._settings, "qwen_api_key", "") or "").strip()
        base_url = (getattr(self._settings, "qwen_base_url", "") or "").strip()
        model = (getattr(self._settings, "qwen_model", "") or "qwen-plus").strip()
        if not api_key or not base_url:
            raise LlmTimeoutError("QWen is not configured (QWEN_API_KEY / QWEN_BASE_URL)")

        url = base_url.rstrip("/") + "/chat/completions"
        body: dict[str, Any] = {
            "model": model,
            "messages": _sanitize_messages(messages),
        }
        if tools:
            body["tools"] = tools

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "rag-as-service/f06",
        }
        msg_count = len(body["messages"])
        tool_count = len(tools or [])
        t0 = time.perf_counter()
        try:
            # Keep a process-level client to reuse TLS connections across turns.
            resp = _QWEN_HTTP_CLIENT.post(url, headers=headers, json=body)
            http_ms = (time.perf_counter() - t0) * 1000.0
            resp.raise_for_status()
            raw = resp.text
        except httpx.HTTPStatusError as exc:
            http_ms = (time.perf_counter() - t0) * 1000.0
            detail = exc.response.text[:500] if exc.response is not None else ""
            code = exc.response.status_code if exc.response is not None else "?"
            logger.warning(
                "QWen HTTP %s after %.1fms: %s", code, http_ms, detail or exc
            )
            raise LlmTimeoutError(f"QWen HTTP {code}: {detail or exc}") from exc
        except httpx.TimeoutException as exc:
            http_ms = (time.perf_counter() - t0) * 1000.0
            logger.warning("QWen request timed out after %.1fms: %s", http_ms, exc)
            raise LlmTimeoutError(f"QWen request timed out: {exc}") from exc
        except httpx.RequestError as exc:
            http_ms = (time.perf_counter() - t0) * 1000.0
            logger.warning("QWen request failed after %.1fms: %s", http_ms, exc)
            raise LlmTimeoutError(f"QWen request failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 — never leak network errors as 500
            http_ms = (time.perf_counter() - t0) * 1000.0
            logger.exception("QWen unexpected failure after %.1fms", http_ms)
            raise LlmTimeoutError(f"QWen unexpected failure: {exc}") from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LlmTimeoutError(f"QWen returned non-JSON: {raw[:200]}") from exc

        if isinstance(payload, dict) and payload.get("error"):
            err = payload["error"]
            msg = err.get("message") if isinstance(err, dict) else str(err)
            raise LlmTimeoutError(f"QWen API error: {msg}")

        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content")
        tool_calls_raw = message.get("tool_calls") or []
        tool_calls: list[ToolCall] = []
        for tc in tool_calls_raw:
            fn = tc.get("function") or {}
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(
                    id=str(tc.get("id") or f"call_{len(tool_calls)}"),
                    name=str(fn.get("name") or ""),
                    arguments=args if isinstance(args, dict) else {},
                )
            )
        usage = payload.get("usage") if isinstance(payload, dict) else None
        usage_bits = ""
        if isinstance(usage, dict):
            usage_bits = (
                f" prompt_tokens={usage.get('prompt_tokens')} "
                f"completion_tokens={usage.get('completion_tokens')} "
                f"total_tokens={usage.get('total_tokens')}"
            )
        logger.info(
            "timing qwen http_ms=%.1f model=%s msg_count=%s tool_defs=%s "
            "reply_tool_calls=%s content_chars=%s%s",
            http_ms,
            model,
            msg_count,
            tool_count,
            len(tool_calls),
            len(content or ""),
            usage_bits,
        )
        return LlmResult(content=content, tool_calls=tool_calls)


_GREETING_MARKERS = frozenset(
    {"你好", "您好", "hello", "hi", "hey", "嗨", "早上好", "下午好", "晚上好"}
)


def _latest_user_text(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return str(msg.get("content") or "").strip()
    return ""


def _is_greeting(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    if normalized in _GREETING_MARKERS:
        return True
    first = normalized.split(maxsplit=1)[0]
    return first in _GREETING_MARKERS or first.rstrip("!?.") in _GREETING_MARKERS


class DevStubLlmClient:
    """Local dev LLM when QWEN_API_KEY is unset and AUTH_STUB_ENABLED=true."""

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LlmResult:
        if messages and messages[-1].get("role") == "tool":
            tool_text = str(messages[-1].get("content") or "")
            if "无命中" in tool_text or "无相关" in tool_text:
                return LlmResult(content=f"{NO_HIT_PHRASE}，无法从知识库找到相关内容。")
            snippet = tool_text
            marker = "--- chunk 1 ---"
            if marker in tool_text:
                snippet = tool_text.split(marker, 1)[1].strip()
                if "--- chunk" in snippet:
                    snippet = snippet.split("--- chunk", 1)[0].strip()
            return LlmResult(content=f"根据知识库检索结果：{snippet[:800]}")

        user_text = _latest_user_text(messages)
        if _is_greeting(user_text):
            return LlmResult(content="你好！有什么可以帮您的吗？")

        if tools:
            return LlmResult(
                tool_calls=[
                    ToolCall(
                        id="dev-stub-search",
                        name=TOOL_SEARCH_KNOWLEDGE,
                        arguments={"query": user_text or "general"},
                    )
                ]
            )
        return LlmResult(content="好的。")
