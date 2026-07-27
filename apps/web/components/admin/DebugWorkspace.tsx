"use client";

import { useState } from "react";
import Link from "next/link";

import {
  postDebugChat,
  postDebugSearch,
  type DebugChatResponse,
  type DebugSearchHit,
} from "@/lib/api";

type Mode = "search" | "chat";

type DebugPanel = "answer" | "topk" | "context" | "history" | "llm";

const DEBUG_PANELS: { id: DebugPanel; label: string }[] = [
  { id: "answer", label: "最终回答" },
  { id: "topk", label: "top-K" },
  { id: "context", label: "上下文" },
  { id: "history", label: "历史" },
  { id: "llm", label: "LLM 调用" },
];

export function DebugWorkspace() {
  const [mode, setMode] = useState<Mode>("search");
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [chatContent, setChatContent] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hits, setHits] = useState<DebugSearchHit[] | null>(null);
  const [chatResult, setChatResult] = useState<DebugChatResponse | null>(null);

  async function onSearch() {
    setBusy(true);
    setError(null);
    setHits(null);
    setChatResult(null);
    try {
      const res = await postDebugSearch({
        query: query.trim(),
        top_k: topK,
      });
      setHits(res.hits);
    } catch (e) {
      setError(e instanceof Error ? e.message : "检索失败");
    } finally {
      setBusy(false);
    }
  }

  async function onChat() {
    setBusy(true);
    setError(null);
    setHits(null);
    setChatResult(null);
    try {
      const res = await postDebugChat({
        content: chatContent.trim(),
        conversation_id: conversationId.trim() || null,
      });
      setChatResult(res);
      if (res.conversation_id) {
        setConversationId(res.conversation_id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "问答失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="widget-admin debug-admin">
      <header className="widget-admin-header">
        <nav className="widget-admin-nav">
          <Link href="/admin">知识库</Link>
          <span aria-hidden="true">/</span>
          <Link href="/admin/widget">Embed Widget</Link>
          <span aria-hidden="true">/</span>
          <span>Debug</span>
        </nav>
        <h1>Admin Debug</h1>
        <p className="widget-admin-lead">
          纯检索验证索引，或运行与 Portal 同路径的 Agent 并展开上下文 / top-K / LLM
          调用。
        </p>
      </header>

      <div className="debug-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          className={`tab${mode === "search" ? " active" : ""}`}
          aria-selected={mode === "search"}
          onClick={() => setMode("search")}
        >
          Search only
        </button>
        <button
          type="button"
          role="tab"
          className={`tab${mode === "chat" ? " active" : ""}`}
          aria-selected={mode === "chat"}
          onClick={() => setMode("chat")}
        >
          Agent debug
        </button>
      </div>

      {error ? (
        <p className="widget-admin-error" role="alert">
          {error}
        </p>
      ) : null}

      {mode === "search" ? (
        <section className="widget-admin-card">
          <h2>检索</h2>
          <label className="widget-admin-label">
            Query
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="输入检索 query"
            />
          </label>
          <label className="widget-admin-label">
            top_k（1–20）
            <input
              type="number"
              min={1}
              max={20}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value) || 5)}
            />
          </label>
          <button
            type="button"
            className="btn primary"
            disabled={busy || !query.trim()}
            onClick={() => void onSearch()}
          >
            {busy ? "检索中…" : "检索"}
          </button>
          {hits ? <HitsList hits={hits} /> : null}
        </section>
      ) : (
        <section className="widget-admin-card">
          <h2>Agent 问答</h2>
          <label className="widget-admin-label">
            问题
            <textarea
              rows={3}
              value={chatContent}
              onChange={(e) => setChatContent(e.target.value)}
              placeholder="与 Portal 等价的用户输入"
            />
          </label>
          <label className="widget-admin-label">
            conversation_id（可选，空=draft 首问）
            <input
              value={conversationId}
              onChange={(e) => setConversationId(e.target.value)}
              placeholder="uuid 或留空"
            />
          </label>
          <button
            type="button"
            className="btn primary"
            disabled={busy || !chatContent.trim()}
            onClick={() => void onChat()}
          >
            {busy ? "运行中…" : "运行 Agent"}
          </button>
          {chatResult ? (
            <ChatDebugView
              key={chatResult.agent_run_id}
              result={chatResult}
            />
          ) : null}
        </section>
      )}
    </main>
  );
}

function HitsList({ hits }: { hits: DebugSearchHit[] }) {
  if (hits.length === 0) {
    return <p className="debug-empty">无命中</p>;
  }
  return (
    <ol className="debug-hits">
      {hits.map((h, i) => (
        <li key={`${h.chunk_id}-${i}`} className="debug-hit">
          <div className="debug-hit-meta">
            <strong>{h.path || "(no path)"}</strong>
            <span>score={h.score.toFixed(3)}</span>
          </div>
          <pre className="debug-pre">{h.content}</pre>
        </li>
      ))}
    </ol>
  );
}

function ChatDebugView({ result }: { result: DebugChatResponse }) {
  const { debug } = result;
  const [panel, setPanel] = useState<DebugPanel>("answer");

  return (
    <div className="debug-panels">
      <div className="debug-tabs" role="tablist" aria-label="Agent debug 面板">
        {DEBUG_PANELS.map((p) => (
          <button
            key={p.id}
            type="button"
            role="tab"
            className={`tab${panel === p.id ? " active" : ""}`}
            aria-selected={panel === p.id}
            onClick={() => setPanel(p.id)}
          >
            {p.label}
          </button>
        ))}
      </div>
      <div className="debug-panel-body" role="tabpanel">
        {panel === "answer" ? (
          <pre className="debug-pre">{result.assistant.content}</pre>
        ) : null}
        {panel === "topk" ? <HitsList hits={debug.top_k_hits} /> : null}
        {panel === "context" ? (
          <pre className="debug-pre">
            {JSON.stringify(debug.context_messages, null, 2)}
          </pre>
        ) : null}
        {panel === "history" ? (
          <pre className="debug-pre">{JSON.stringify(debug.history, null, 2)}</pre>
        ) : null}
        {panel === "llm" ? (
          <pre className="debug-pre">{JSON.stringify(debug.llm_calls, null, 2)}</pre>
        ) : null}
      </div>
    </div>
  );
}
