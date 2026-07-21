"use client";

import { useCallback, useEffect, useState } from "react";

import { Composer } from "@/components/chat/Composer";
import { ConversationSidebar } from "@/components/chat/ConversationSidebar";
import { MessageList } from "@/components/chat/MessageList";
import {
  archiveConversation,
  createConversation,
  deleteConversation,
  listConversations,
  listMessages,
  postMessageStream,
  renameConversation,
  unarchiveConversation,
  type Conversation,
  type ConversationStatus,
  type Message,
} from "@/lib/api";

function newTempId(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function ChatWorkspace() {
  const [statusFilter, setStatusFilter] =
    useState<ConversationStatus>("active");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selected = conversations.find((c) => c.id === selectedId) ?? null;
  const canCompose = selected?.status === "active";

  const refreshList = useCallback(async (status: ConversationStatus) => {
    const items = await listConversations(status);
    setConversations(items);
    return items;
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setError(null);
      try {
        const items = await refreshList(statusFilter);
        if (cancelled) return;
        if (selectedId && !items.some((c) => c.id === selectedId)) {
          setSelectedId(null);
          setMessages([]);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "加载失败");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [statusFilter, refreshList, selectedId]);

  async function openConversation(id: string) {
    setSelectedId(id);
    setError(null);
    try {
      setMessages(await listMessages(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载消息失败");
      setMessages([]);
    }
  }

  async function handleCreate() {
    setBusy(true);
    setError(null);
    try {
      setStatusFilter("active");
      const conv = await createConversation();
      await refreshList("active");
      await openConversation(conv.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleArchive(id: string) {
    setBusy(true);
    setError(null);
    try {
      await archiveConversation(id);
      const items = await refreshList(statusFilter);
      if (selectedId === id) {
        setSelectedId(null);
        setMessages([]);
      }
      if (!items.some((c) => c.id === selectedId)) {
        /* already cleared */
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "归档失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleUnarchive(id: string) {
    setBusy(true);
    setError(null);
    try {
      await unarchiveConversation(id);
      setStatusFilter("active");
      await refreshList("active");
      await openConversation(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "取消归档失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm("确定软删除该会话？删除后列表不可见。")) return;
    setBusy(true);
    setError(null);
    try {
      await deleteConversation(id);
      await refreshList(statusFilter);
      if (selectedId === id) {
        setSelectedId(null);
        setMessages([]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleRename(id: string, title: string) {
    setBusy(true);
    setError(null);
    try {
      await renameConversation(id, title);
      await refreshList(statusFilter);
    } catch (e) {
      setError(e instanceof Error ? e.message : "重命名失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleSend(content: string) {
    if (!selectedId) return;
    setError(null);
    const t0 = performance.now();
    const nowIso = new Date().toISOString();
    const tempUserId = newTempId("temp-user");
    const tempAssistantId = newTempId("temp-assistant");
    const tempUser: Message = {
      id: tempUserId,
      conversation_id: selectedId,
      tenant_id: selected?.tenant_id ?? "",
      role: "user",
      content,
      create_at: nowIso,
      update_at: nowIso,
      meta: null,
      agent_run_id: null,
    };
    const tempAssistant: Message = {
      id: tempAssistantId,
      conversation_id: selectedId,
      tenant_id: selected?.tenant_id ?? "",
      role: "assistant",
      content: "思考中…",
      create_at: nowIso,
      update_at: nowIso,
      meta: null,
      agent_run_id: null,
    };
    setMessages((prev) => [...prev, tempUser, tempAssistant]);
    try {
      const turn = await postMessageStream(selectedId, content, {
        onProgress: (_stage, elapsedMs) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === tempAssistantId
                ? { ...m, content: `思考中… ${(elapsedMs / 1000).toFixed(1)}s` }
                : m,
            ),
          );
        },
      });
      const afterFetch = performance.now();
      setMessages((prev) =>
        prev.flatMap((m) => {
          if (m.id === tempUserId) return [turn.user];
          if (m.id === tempAssistantId) return [turn.assistant];
          return [m];
        }),
      );
      if (turn.conversation_title) {
        setConversations((prev) =>
          prev.map((c) =>
            c.id === selectedId
              ? { ...c, title: turn.conversation_title as string }
              : c,
          ),
        );
      }
      console.info(
        `[timing] chat.ui apply_ms=${(performance.now() - afterFetch).toFixed(1)} ` +
          `handle_send_total_ms=${(performance.now() - t0).toFixed(1)}`,
      );
    } catch (e) {
      setMessages((prev) =>
        prev.filter((m) => m.id !== tempAssistantId && m.id !== tempUserId),
      );
      setError(e instanceof Error ? e.message : "发送失败");
      throw e;
    }
  }

  return (
    <div className="chat-shell">
      <ConversationSidebar
        conversations={conversations}
        statusFilter={statusFilter}
        selectedId={selectedId}
        busy={busy}
        onStatusFilter={setStatusFilter}
        onSelect={(id) => void openConversation(id)}
        onCreate={() => void handleCreate()}
        onArchive={(id) => void handleArchive(id)}
        onUnarchive={(id) => void handleUnarchive(id)}
        onRename={(id, title) => void handleRename(id, title)}
        onDelete={(id) => void handleDelete(id)}
      />
      <main className="chat-main">
        {error && <div className="banner error">{error}</div>}
        {!selected ? (
          <div className="messages empty">选择或新建一个会话</div>
        ) : (
          <>
            <header className="chat-header">
              <h2>{selected.title}</h2>
              <span className="status-label">{selected.status}</span>
            </header>
            <MessageList
              messages={messages}
              emptyHint="尚无消息。发送一条即可开始对话。"
            />
            <Composer
              disabled={!canCompose}
              disabledReason={
                canCompose
                  ? undefined
                  : "已归档会话不可发消息，请先取消归档。"
              }
              onSend={handleSend}
            />
          </>
        )}
      </main>
    </div>
  );
}
