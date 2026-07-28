"use client";

import { useEffect, useRef, useState } from "react";

import type { FolderNode } from "@/lib/api";

export type KnowledgeBaseItem = FolderNode;

type Props = {
  search: string;
  selectedNav: "home" | "knowledge" | "reviewTasks" | "permissions";
  selectedPermissionSection: "members";
  knowledgeBases: KnowledgeBaseItem[];
  currentFolderId: string | null;
  busy: boolean;
  canReviewTasks: boolean;
  onSearch: (q: string) => void;
  onSelectNav: (nav: "home" | "knowledge" | "reviewTasks" | "permissions") => void;
  onSelectPermissionSection: (section: "members") => void;
  onSelectKnowledgeBase: (id: string) => void;
  onCreateKnowledgeBase: () => void;
  onRenameKnowledgeBase: (id: string, currentName: string) => void;
  onDeleteKnowledgeBase: (id: string, currentName: string) => void;
};

function IconMore() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden>
      <circle cx="5" cy="12" r="1.8" fill="currentColor" />
      <circle cx="12" cy="12" r="1.8" fill="currentColor" />
      <circle cx="19" cy="12" r="1.8" fill="currentColor" />
    </svg>
  );
}

function IconRename() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden>
      <path
        fill="currentColor"
        d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zm2.92 2.83H5v-.92l9.06-9.06.92.92L5.92 20.08zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"
      />
    </svg>
  );
}

function IconDelete() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden>
      <path
        fill="currentColor"
        d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"
      />
    </svg>
  );
}

export function DocSidebar({
  search,
  selectedNav,
  selectedPermissionSection,
  knowledgeBases,
  currentFolderId,
  busy,
  canReviewTasks,
  onSearch,
  onSelectNav,
  onSelectPermissionSection,
  onSelectKnowledgeBase,
  onCreateKnowledgeBase,
  onRenameKnowledgeBase,
  onDeleteKnowledgeBase,
}: Props) {
  const [knowledgeExpanded, setKnowledgeExpanded] = useState(false);
  const [permissionsExpanded, setPermissionsExpanded] = useState(true);
  const [menuForId, setMenuForId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!knowledgeExpanded) setMenuForId(null);
  }, [knowledgeExpanded]);

  useEffect(() => {
    if (selectedNav !== "knowledge" && selectedNav !== "reviewTasks") {
      setKnowledgeExpanded(false);
      setMenuForId(null);
    }
  }, [selectedNav]);

  useEffect(() => {
    if (!menuForId) return;
    function onPointerDown(e: PointerEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuForId(null);
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuForId(null);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [menuForId]);

  function handleToggleKnowledge() {
    if (knowledgeExpanded) {
      setKnowledgeExpanded(false);
      setMenuForId(null);
      return;
    }
    setKnowledgeExpanded(true);
    if (selectedNav !== "knowledge") {
      onSelectNav("knowledge");
    }
  }

  function handleTogglePermissions() {
    if (permissionsExpanded) {
      setPermissionsExpanded(false);
      return;
    }
    setPermissionsExpanded(true);
    if (selectedNav !== "permissions") {
      onSelectNav("permissions");
    }
  }

  return (
    <aside className="sidebar kb-sidebar">
      <div className="sidebar-header kb-sidebar-header kb-brand-row">
        <button type="button" className="kb-nav-toggle" aria-label="折叠导航">
          ☰
        </button>
        <div className="kb-brand-mark" aria-hidden>
          ◢
        </div>
        <h1 className="sidebar-title kb-brand-title">RAG As Service</h1>
      </div>

      <input
        className="doc-search"
        type="search"
        placeholder="搜索文档标题…"
        value={search}
        onChange={(e) => onSearch(e.target.value)}
        aria-label="搜索文档标题"
      />

      <nav className="kb-app-nav" aria-label="主导航">
        <button
          type="button"
          className={`kb-app-nav-item${selectedNav === "home" ? " active" : ""}`}
          onClick={() => onSelectNav("home")}
        >
          <span className="kb-app-nav-icon" aria-hidden>
            ⌂
          </span>
          <span>主页</span>
        </button>

        <div className="kb-nav-group">
          <button
            type="button"
            className={`kb-app-nav-item${selectedNav === "knowledge" && !currentFolderId ? " active" : ""}`}
            onClick={handleToggleKnowledge}
            aria-expanded={knowledgeExpanded}
          >
            <span className="kb-app-nav-db-icon" aria-hidden>
              <span />
              <span />
              <span />
            </span>
            <span>知识库</span>
          </button>
          {knowledgeExpanded ? (
            <ul className="kb-nav-sublist">
              {canReviewTasks ? (
                <li>
                  <button
                    type="button"
                    className={`kb-nav-subitem${selectedNav === "reviewTasks" ? " active" : ""}`}
                    onClick={() => {
                      setMenuForId(null);
                      setKnowledgeExpanded(true);
                      onSelectNav("reviewTasks");
                    }}
                  >
                    待审核任务
                  </button>
                </li>
              ) : null}
              {knowledgeBases.map((kb) => {
                const active =
                  selectedNav === "knowledge" && currentFolderId === kb.folder_id;
                const menuOpen = menuForId === kb.folder_id;
                return (
                  <li key={kb.folder_id} className="kb-nav-kb-row">
                    <button
                      type="button"
                      className={`kb-nav-subitem kb-nav-kb-main${active ? " active" : ""}`}
                      onClick={() => {
                        setMenuForId(null);
                        setKnowledgeExpanded(true);
                        onSelectKnowledgeBase(kb.folder_id);
                      }}
                    >
                      <span className="kb-nav-kb-name">{kb.name}</span>
                    </button>
                    <div
                      className="kb-nav-kb-more-wrap"
                      ref={menuOpen ? menuRef : undefined}
                    >
                      <button
                        type="button"
                        className={`kb-nav-kb-more${menuOpen ? " open" : ""}`}
                        aria-label={`${kb.name} 更多操作`}
                        aria-expanded={menuOpen}
                        disabled={busy}
                        onClick={(e) => {
                          e.stopPropagation();
                          setMenuForId(menuOpen ? null : kb.folder_id);
                        }}
                      >
                        <IconMore />
                      </button>
                      {menuOpen ? (
                        <div className="kb-nav-kb-menu" role="menu">
                          <button
                            type="button"
                            className="kb-icon-btn"
                            role="menuitem"
                            title="修改"
                            aria-label={`修改 ${kb.name}`}
                            disabled={busy}
                            onClick={() => {
                              setMenuForId(null);
                              onRenameKnowledgeBase(kb.folder_id, kb.name);
                            }}
                          >
                            <IconRename />
                          </button>
                          <button
                            type="button"
                            className="kb-icon-btn danger"
                            role="menuitem"
                            title="删除"
                            aria-label={`删除 ${kb.name}`}
                            disabled={busy}
                            onClick={() => {
                              setMenuForId(null);
                              onDeleteKnowledgeBase(kb.folder_id, kb.name);
                            }}
                          >
                            <IconDelete />
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </li>
                );
              })}
              <li>
                <button
                  type="button"
                  className="kb-nav-subitem kb-nav-subitem-add"
                  disabled={busy}
                  onClick={onCreateKnowledgeBase}
                >
                  + 创建知识库
                </button>
              </li>
              {knowledgeBases.length === 0 ? (
                <li className="kb-nav-sub-empty">暂无知识库</li>
              ) : null}
            </ul>
          ) : null}
        </div>

        <div className="kb-nav-group">
          <button
            type="button"
            className={`kb-app-nav-item${selectedNav === "permissions" ? " active" : ""}`}
            onClick={handleTogglePermissions}
            aria-expanded={permissionsExpanded}
          >
            <span className="kb-app-nav-icon" aria-hidden>
              ⚿
            </span>
            <span>权限管理</span>
          </button>
          {permissionsExpanded ? (
            <ul className="kb-nav-sublist">
              <li>
                <button
                  type="button"
                  className={`kb-nav-subitem${selectedNav === "permissions" && selectedPermissionSection === "members" ? " active" : ""}`}
                  onClick={() => {
                    onSelectNav("permissions");
                    onSelectPermissionSection("members");
                  }}
                >
                  成员管理
                </button>
              </li>
            </ul>
          ) : null}
        </div>
      </nav>
    </aside>
  );
}
