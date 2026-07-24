"use client";

import { useEffect, useId, useRef, useState } from "react";

import { SidebarPanelIcon } from "@/components/chat/SidebarPanelIcon";
import { NewTaskIcon } from "@/components/chat/NewTaskIcon";
import type { Conversation, ConversationStatus } from "@/lib/api";

type Props = {
  conversations: Conversation[];
  statusFilter: ConversationStatus;
  selectedId: string | null;
  busy: boolean;
  collapsed: boolean;
  mobileOpen: boolean;
  onStatusFilter: (s: ConversationStatus) => void;
  onSelect: (id: string) => void;
  onNewTask: () => void;
  onArchive: (id: string) => void;
  onUnarchive: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  onToggleCollapse: () => void;
  onCloseMobile: () => void;
};

export function ConversationSidebar({
  conversations,
  statusFilter,
  selectedId,
  busy,
  collapsed,
  mobileOpen,
  onStatusFilter,
  onSelect,
  onNewTask,
  onArchive,
  onUnarchive,
  onRename,
  onDelete,
  onToggleCollapse,
  onCloseMobile,
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

  function handleSelect(id: string) {
    onSelect(id);
    onCloseMobile();
  }

  return (
    <>
      {mobileOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label="关闭侧栏"
          onClick={onCloseMobile}
        />
      )}
      <aside
        className={[
          "sidebar",
          collapsed ? "sidebar-collapsed" : "",
          mobileOpen ? "sidebar-mobile-open" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        data-testid="portal-sidebar"
      >
        <div className="sidebar-top">
          <div className="sidebar-header">
            <img
              className="sidebar-brand"
              src="/brand-cube.png"
              alt=""
              width={28}
              height={28}
            />
            <button
              type="button"
              className="btn ghost sidebar-collapse"
              onClick={onToggleCollapse}
              aria-label="折叠侧栏"
              title="折叠侧栏"
            >
              <SidebarPanelIcon />
            </button>
          </div>

          <button
            type="button"
            className="btn primary new-task-btn"
            disabled={busy}
            data-testid="new-task"
            onClick={() => {
              onNewTask();
              onCloseMobile();
            }}
          >
            <NewTaskIcon />
            New task
          </button>

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
        </div>

        <ul className="conv-list" data-testid="conversation-list">
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
                data-conversation-id={c.id}
              >
                <div className="conv-row">
                  <button
                    type="button"
                    className="conv-main"
                    onClick={() => handleSelect(c.id)}
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

        <div className="sidebar-footer">
          <div className="sidebar-footer-row">
            <a
              className="sidebar-footer-link"
              href="https://lxzxai.com/login"
            >
              <svg
                className="sidebar-footer-icon"
                viewBox="0 0 16 16"
                width="14"
                height="14"
                aria-hidden="true"
                focusable="false"
              >
                <circle
                  cx="8"
                  cy="5.25"
                  r="2.5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.4"
                />
                <path
                  d="M3.25 13.25c0-2.35 2.13-3.75 4.75-3.75s4.75 1.4 4.75 3.75"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                />
              </svg>
              Me
            </a>
            <a className="sidebar-footer-link" href="/admin">
              <svg
                className="sidebar-footer-icon"
                viewBox="0 0 16 16"
                width="14"
                height="14"
                aria-hidden="true"
                focusable="false"
              >
                <path
                  d="M6.55 1.75h2.9l.22 1.35c.4.14.77.35 1.1.61l1.3-.5 1.45 2.5-1.05.9c.08.32.12.65.12.99s-.04.67-.12.99l1.05.9-1.45 2.5-1.3-.5c-.33.26-.7.47-1.1.61l-.22 1.35H6.55l-.22-1.35a4.4 4.4 0 0 1-1.1-.61l-1.3.5-1.45-2.5 1.05-.9A4.1 4.1 0 0 1 3.4 7.6c0-.34.04-.67.12-.99l-1.05-.9 1.45-2.5 1.3.5c.33-.26.7-.47 1.1-.61l.23-1.35Z"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.3"
                  strokeLinejoin="round"
                />
                <circle
                  cx="8"
                  cy="8"
                  r="1.85"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.3"
                />
              </svg>
              Settings
            </a>
          </div>
        </div>
      </aside>
    </>
  );
}
