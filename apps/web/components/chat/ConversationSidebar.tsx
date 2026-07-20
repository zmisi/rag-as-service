"use client";

import type { Conversation, ConversationStatus } from "@/lib/api";

type Props = {
  conversations: Conversation[];
  statusFilter: ConversationStatus;
  selectedId: string | null;
  busy: boolean;
  onStatusFilter: (s: ConversationStatus) => void;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onArchive: (id: string) => void;
  onUnarchive: (id: string) => void;
  onDelete: (id: string) => void;
};

export function ConversationSidebar({
  conversations,
  statusFilter,
  selectedId,
  busy,
  onStatusFilter,
  onSelect,
  onCreate,
  onArchive,
  onUnarchive,
  onDelete,
}: Props) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1 className="sidebar-title">会话</h1>
        <button
          type="button"
          className="btn primary"
          disabled={busy}
          onClick={onCreate}
        >
          新会话
        </button>
      </div>

      <div className="tabs" role="tablist">
        <button
          type="button"
          role="tab"
          className={statusFilter === "active" ? "tab active" : "tab"}
          aria-selected={statusFilter === "active"}
          onClick={() => onStatusFilter("active")}
        >
          进行中
        </button>
        <button
          type="button"
          role="tab"
          className={statusFilter === "archived" ? "tab active" : "tab"}
          aria-selected={statusFilter === "archived"}
          onClick={() => onStatusFilter("archived")}
        >
          已归档
        </button>
      </div>

      <ul className="conv-list">
        {conversations.length === 0 && (
          <li className="empty-hint">暂无会话</li>
        )}
        {conversations.map((c) => (
          <li
            key={c.id}
            className={c.id === selectedId ? "conv-item selected" : "conv-item"}
          >
            <button
              type="button"
              className="conv-main"
              onClick={() => onSelect(c.id)}
            >
              <span className="conv-title">{c.title}</span>
            </button>
            <div className="conv-actions">
              {c.status === "active" ? (
                <button
                  type="button"
                  className="btn ghost"
                  disabled={busy}
                  onClick={() => onArchive(c.id)}
                >
                  归档
                </button>
              ) : (
                <button
                  type="button"
                  className="btn ghost"
                  disabled={busy}
                  onClick={() => onUnarchive(c.id)}
                >
                  取消归档
                </button>
              )}
              <button
                type="button"
                className="btn danger"
                disabled={busy}
                onClick={() => onDelete(c.id)}
              >
                删除
              </button>
            </div>
          </li>
        ))}
      </ul>
    </aside>
  );
}
