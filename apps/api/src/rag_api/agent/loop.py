"""Agent Loop: model-driven ReAct without pre-intent classification."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from rag_api.agent.constants import (
    ERROR_REPLY,
    MAX_STEPS,
    NO_HIT_PHRASE,
    TOOL_SEARCH_KNOWLEDGE,
    TRUNCATED_REPLY,
)
from rag_api.agent.context import assemble_messages
from rag_api.agent.tools import ToolExecutor, tool_definitions
from rag_api.clients.llm import LlmClient, LlmResult, LlmTimeoutError, ToolCall
from rag_api.db.models import Message
from rag_api.indexing.search import KnowledgeSearcher
from rag_api.observability.agent_log import dump_json, log_agent, snip

logger = logging.getLogger(__name__)
timing_log = logging.getLogger("rag_api.timing")


@dataclass
class LoopStepRecord:
    step_type: str
    tool_name: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class LoopResult:
    reply: str
    status: str  # completed | truncated | error
    used_search: bool
    step_count: int
    steps: list[LoopStepRecord]
    error: str | None = None


class AgentLoop:
    def __init__(
        self,
        *,
        llm: LlmClient,
        searcher: KnowledgeSearcher,
        tenant_id: UUID,
    ) -> None:
        self._llm = llm
        self._tools = ToolExecutor(searcher, tenant_id)

    def run(self, *, history: list[Message], user_content: str) -> LoopResult:
        steps: list[LoopStepRecord] = []
        used_search = False
        pending_tools: list[dict[str, Any]] = []
        step_count = 0
        # One-shot recovery when model claims no-hit without calling search.
        harness_forced_search_done = False
        loop_t0 = time.perf_counter()
        log_agent(
            "loop.start",
            tenant_id=str(self._tools._tenant_id),
            max_steps=MAX_STEPS,
            history_count=len(history),
            user_chars=len(user_content),
            user=snip(user_content, 200),
        )

        try:
            for _ in range(MAX_STEPS):
                step_count += 1
                step_t0 = time.perf_counter()
                log_agent(
                    "loop.step.begin",
                    step=step_count,
                    max_steps=MAX_STEPS,
                    pending_tool_msgs=len(pending_tools),
                    used_search=int(used_search),
                )

                t_assemble = time.perf_counter()
                messages = assemble_messages(
                    history=history,
                    user_content=user_content,
                    tool_messages=pending_tools or None,
                )
                assemble_ms = (time.perf_counter() - t_assemble) * 1000.0

                t_llm = time.perf_counter()
                result = self._llm.complete(messages, tools=tool_definitions())
                llm_ms = (time.perf_counter() - t_llm) * 1000.0
                usage = result.usage or {}
                steps.append(
                    LoopStepRecord(
                        step_type="llm",
                        payload={
                            "content": result.content,
                            "tool_calls": [
                                {"id": t.id, "name": t.name, "arguments": t.arguments}
                                for t in result.tool_calls
                            ],
                            "usage": usage,
                            "finish_reason": result.finish_reason,
                            "timing_ms": {
                                "assemble": round(assemble_ms, 1),
                                "llm": round(llm_ms, 1),
                            },
                        },
                    )
                )
                timing_log.info(
                    "timing agent_loop step=%s assemble_ms=%.1f llm_ms=%.1f "
                    "msg_count=%s tool_calls=%s prompt_tokens=%s completion_tokens=%s",
                    step_count,
                    assemble_ms,
                    llm_ms,
                    len(messages),
                    len(result.tool_calls),
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                )
                log_agent(
                    "loop.step.llm",
                    step=step_count,
                    assemble_ms=f"{assemble_ms:.1f}",
                    llm_ms=f"{llm_ms:.1f}",
                    msg_count=len(messages),
                    model=result.model,
                    finish_reason=result.finish_reason,
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                    total_tokens=usage.get("total_tokens"),
                    tool_call_count=len(result.tool_calls),
                    content_chars=len(result.content or ""),
                    content=snip(result.content, 400),
                )

                tool_calls = list(result.tool_calls)
                harness_forced = False
                if not tool_calls:
                    reply_probe = (result.content or "").strip()
                    if (
                        NO_HIT_PHRASE in reply_probe
                        and not used_search
                        and not harness_forced_search_done
                        and step_count < MAX_STEPS
                    ):
                        harness_forced_search_done = True
                        harness_forced = True
                        tool_calls = [
                            ToolCall(
                                id=f"harness-search-{step_count}",
                                name=TOOL_SEARCH_KNOWLEDGE,
                                arguments={"query": user_content},
                            )
                        ]
                        log_agent(
                            "loop.grounding.force_search",
                            step=step_count,
                            reason="premature_no_hit",
                            query=snip(user_content, 200),
                        )

                if tool_calls:
                    # Execute first tool call per step (Phase 1 simple harness)
                    tc = tool_calls[0]
                    log_agent(
                        "loop.tool.request",
                        step=step_count,
                        tool=tc.name,
                        tool_call_id=tc.id,
                        arguments=dump_json(tc.arguments, 500),
                        whitelist_ok=int(tc.name in (TOOL_SEARCH_KNOWLEDGE,)),
                        harness_forced=int(harness_forced),
                    )
                    if tc.name not in (TOOL_SEARCH_KNOWLEDGE,) and tc.name:
                        # Whitelist violation: terminate without executing
                        steps.append(
                            LoopStepRecord(
                                step_type="tool_call",
                                tool_name=tc.name,
                                payload={"arguments": tc.arguments, "rejected": True},
                            )
                        )
                        t_tool = time.perf_counter()
                        exec_result = self._tools.execute(tc.name, tc.arguments)
                        tool_ms = (time.perf_counter() - t_tool) * 1000.0
                        timing_log.info(
                            "timing agent_loop step=%s tool=%s rejected=1 tool_ms=%.1f",
                            step_count,
                            tc.name,
                            tool_ms,
                        )
                        log_agent(
                            "loop.tool.rejected",
                            step=step_count,
                            tool=tc.name,
                            tool_ms=f"{tool_ms:.1f}",
                            error=exec_result.error,
                        )
                        steps.append(
                            LoopStepRecord(
                                step_type="tool_result",
                                tool_name=tc.name,
                                payload=exec_result.payload,
                            )
                        )
                        steps.append(
                            LoopStepRecord(
                                step_type="final",
                                payload={"reason": "unknown_tool"},
                            )
                        )
                        return LoopResult(
                            reply="抱歉，模型请求了不被允许的工具，已终止本轮。",
                            status="error",
                            used_search=used_search,
                            step_count=step_count,
                            steps=steps,
                            error=exec_result.error,
                        )

                    steps.append(
                        LoopStepRecord(
                            step_type="tool_call",
                            tool_name=tc.name,
                            payload={"arguments": tc.arguments, "id": tc.id},
                        )
                    )
                    t_tool = time.perf_counter()
                    exec_result = self._tools.execute(tc.name, tc.arguments)
                    tool_ms = (time.perf_counter() - t_tool) * 1000.0
                    hit_count = len((exec_result.payload or {}).get("chunks") or [])
                    timing_log.info(
                        "timing agent_loop step=%s tool=%s tool_ms=%.1f hit_count=%s",
                        step_count,
                        tc.name,
                        tool_ms,
                        hit_count,
                    )
                    log_agent(
                        "loop.tool.result",
                        step=step_count,
                        tool=tc.name,
                        tool_ms=f"{tool_ms:.1f}",
                        ok=int(exec_result.ok),
                        hit_count=hit_count,
                        content_for_llm_chars=len(exec_result.content_for_llm or ""),
                        query=(exec_result.payload or {}).get("query"),
                    )
                    if exec_result.used_search:
                        used_search = True
                    steps.append(
                        LoopStepRecord(
                            step_type="tool_result",
                            tool_name=tc.name,
                            payload={
                                **(exec_result.payload or {}),
                                "timing_ms": {"tool": round(tool_ms, 1)},
                            },
                        )
                    )
                    pending_tools = list(pending_tools)
                    pending_tools.append(
                        {
                            "role": "assistant",
                            # Drop premature no-hit text when harness injects the tool call.
                            "content": "" if harness_forced else (result.content or ""),
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.name,
                                        "arguments": _json_args(tc),
                                    },
                                }
                            ],
                        }
                    )
                    pending_tools.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": exec_result.content_for_llm,
                        }
                    )
                    timing_log.info(
                        "timing agent_loop step=%s total_ms=%.1f continue=1",
                        step_count,
                        (time.perf_counter() - step_t0) * 1000.0,
                    )
                    log_agent(
                        "loop.step.continue",
                        step=step_count,
                        step_ms=f"{(time.perf_counter() - step_t0) * 1000.0:.1f}",
                        pending_tool_msgs=len(pending_tools),
                    )
                    continue

                # Final answer
                reply = (result.content or "").strip() or _default_final(used_search)
                steps.append(LoopStepRecord(step_type="final", payload={"content": reply}))
                timing_log.info(
                    "timing agent_loop done status=completed steps=%s total_ms=%.1f",
                    step_count,
                    (time.perf_counter() - loop_t0) * 1000.0,
                )
                log_agent(
                    "loop.done",
                    status="completed",
                    steps=step_count,
                    used_search=int(used_search),
                    total_ms=f"{(time.perf_counter() - loop_t0) * 1000.0:.1f}",
                    reply_chars=len(reply),
                    reply=snip(reply, 500),
                )
                return LoopResult(
                    reply=reply,
                    status="completed",
                    used_search=used_search,
                    step_count=step_count,
                    steps=steps,
                )

            # Max steps exhausted
            t_summary = time.perf_counter()
            log_agent("loop.force_summary", steps=step_count, max_steps=MAX_STEPS)
            summary = _force_summary(self._llm, history, user_content, pending_tools, used_search)
            timing_log.info(
                "timing agent_loop force_summary_ms=%.1f total_ms=%.1f",
                (time.perf_counter() - t_summary) * 1000.0,
                (time.perf_counter() - loop_t0) * 1000.0,
            )
            steps.append(
                LoopStepRecord(step_type="final", payload={"content": summary, "truncated": True})
            )
            log_agent(
                "loop.done",
                status="truncated",
                steps=step_count,
                used_search=int(used_search),
                total_ms=f"{(time.perf_counter() - loop_t0) * 1000.0:.1f}",
                reply_chars=len(summary),
            )
            return LoopResult(
                reply=summary,
                status="truncated",
                used_search=used_search,
                step_count=step_count,
                steps=steps,
            )
        except LlmTimeoutError as exc:
            logger.warning("Agent loop LLM timeout: %s", exc)
            timing_log.warning(
                "timing agent_loop done status=error reason=llm_timeout "
                "steps=%s total_ms=%.1f error=%s",
                step_count,
                (time.perf_counter() - loop_t0) * 1000.0,
                exc,
            )
            log_agent(
                "loop.done",
                status="error",
                reason="llm_timeout",
                steps=step_count,
                total_ms=f"{(time.perf_counter() - loop_t0) * 1000.0:.1f}",
                error=str(exc),
            )
            steps.append(LoopStepRecord(step_type="final", payload={"error": str(exc)}))
            return LoopResult(
                reply=ERROR_REPLY,
                status="error",
                used_search=used_search,
                step_count=step_count,
                steps=steps,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 — never 500 the chat turn on LLM/tool faults
            logger.exception("Agent loop unexpected failure")
            timing_log.exception(
                "timing agent_loop done status=error reason=unexpected "
                "steps=%s total_ms=%.1f",
                step_count,
                (time.perf_counter() - loop_t0) * 1000.0,
            )
            log_agent(
                "loop.done",
                status="error",
                reason="unexpected",
                steps=step_count,
                total_ms=f"{(time.perf_counter() - loop_t0) * 1000.0:.1f}",
                error=str(exc),
            )
            steps.append(LoopStepRecord(step_type="final", payload={"error": str(exc)}))
            return LoopResult(
                reply=ERROR_REPLY,
                status="error",
                used_search=used_search,
                step_count=step_count,
                steps=steps,
                error=str(exc),
            )


def _json_args(tc: ToolCall) -> str:
    import json

    return json.dumps(tc.arguments, ensure_ascii=False)


def _default_final(used_search: bool) -> str:
    if used_search:
        return NO_HIT_PHRASE
    return "好的。"


def _force_summary(
    llm: LlmClient,
    history: list[Message],
    user_content: str,
    pending_tools: list[dict[str, Any]],
    used_search: bool,
) -> str:
    try:
        messages = assemble_messages(
            history=history,
            user_content=user_content + f"\n\n（系统：请在不调用工具的情况下给出总结性回复。{TRUNCATED_REPLY}）",
            tool_messages=pending_tools or None,
        )
        # No tools on forced summary
        result: LlmResult = llm.complete(messages, tools=None)
        text = (result.content or "").strip()
        if text:
            return f"{TRUNCATED_REPLY}\n{text}"
    except LlmTimeoutError:
        pass
    if used_search:
        return f"{TRUNCATED_REPLY}\n{NO_HIT_PHRASE}"
    return TRUNCATED_REPLY
