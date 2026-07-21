"use client";

import { useEffect, useId, useRef, useState } from "react";

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
  onRename: (id: string, title: string) => void;
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
  onRename,
  onDelete,
}: Props) {
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const menuLabelId = useId();

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!menuRef.current) return;
      if (!menuRef.current.contains(e.target as Node)) {
        setMenuOpenId(null);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuOpenId(null);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  function handleRename(c: Conversation) {
    setMenuOpenId(null);
    const next = window.prompt("重命名会话", c.title);
    if (next === null) return;
    const title = next.trim();
    if (!title || title === c.title) return;
    onRename(c.id, title);
  }

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
        {conversations.map((c) => {
          const open = menuOpenId === c.id;
          return (
            <li
              key={c.id}
              className={
                c.id === selectedId ? "conv-item selected" : "conv-item"
              }
            >
              <div className="conv-row">
                <button
                  type="button"
                  className="conv-main"
                  onClick={() => onSelect(c.id)}
                >
                  <span className="conv-title">{c.title}</span>
                </button>
                <div
                  className="conv-menu"
                  ref={open ? menuRef : undefined}
                >
                  <button
                    type="button"
                    className="btn icon-more"
                    disabled={busy}
                    aria-haspopup="menu"
                    aria-expanded={open}
                    aria-controls={open ? menuLabelId : undefined}
                    aria-label="会话操作"
                    onClick={(e) => {
                      e.stopPropagation();
                      setMenuOpenId(open ? null : c.id);
                    }}
                  >
                    ⋯
                  </button>
                  {open && (
                    <div
                      className="conv-menu-dropdown"
                      id={menuLabelId}
                      role="menu"
                    >
                      <button
                        type="button"
                        role="menuitem"
                        className="conv-menu-item"
                        disabled={busy}
                        onClick={() => handleRename(c)}
                      >
                        重命名
                      </button>
                      {c.status === "active" ? (
                        <button
                          type="button"
                          role="menuitem"
                          className="conv-menu-item"
                          disabled={busy}
                          onClick={() => {
                            setMenuOpenId(null);
                            onArchive(c.id);
                          }}
                        >
                          归档
                        </button>
                      ) : (
                        <button
                          type="button"
                          role="menuitem"
                          className="conv-menu-item"
                          disabled={busy}
                          onClick={() => {
                            setMenuOpenId(null);
                            onUnarchive(c.id);
                          }}
                        >
                          取消归档
                        </button>
                      )}
                      <button
                        type="button"
                        role="menuitem"
                        className="conv-menu-item danger"
                        disabled={busy}
                        onClick={() => {
                          setMenuOpenId(null);
                          onDelete(c.id);
                        }}
                      >
                        删除
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
