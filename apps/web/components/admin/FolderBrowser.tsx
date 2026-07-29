"use client";

import { useEffect, useMemo, useState } from "react";

import type { FolderLayer, FolderLayerDoc, FolderNode } from "@/lib/api";

const PAGE_SIZE = 20;
type SortKey = "doc_name" | "create_at";
type SortDirection = "asc" | "desc";

type Props = {
  currentFolderId: string | null;
  layer: FolderLayer | null;
  tree: FolderNode[];
  busy: boolean;
  titleOverride?: string;
  subtitleOverride?: string;
  documentsOverride?: FolderLayerDoc[];
  emptyTextOverride?: string;
  searchPlaceholder?: string;
  hideCreateActions?: boolean;
  hideSelectionActions?: boolean;
  hideRowActions?: boolean;
  selectionActionLabel?: string;
  onSelectionAction?: (items: { id: string; name: string }[]) => void;
  onCreateDoc: () => void;
  onCreateFolder: () => void;
  onOpenDoc: (id: string) => void;
  onRenameDoc: (id: string, currentName: string) => void;
  onDownloadDoc: (id: string, currentName: string) => void;
  onDeleteDoc: (id: string, currentName: string) => void;
  onDeleteDocs: (items: { id: string; name: string }[]) => void;
  onPublishDoc?: (id: string, currentName: string) => void;
};

function formatDate(value: string | null) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function displayText(value?: string | null) {
  return value && value.trim() ? value : "-";
}

function IconRename() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden>
      <path
        fill="currentColor"
        d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zm2.92 2.83H5v-.92l9.06-9.06.92.92L5.92 20.08zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"
      />
    </svg>
  );
}

function IconDownload() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden>
      <path
        fill="currentColor"
        d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"
      />
    </svg>
  );
}

function IconPublish() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden>
      <path
        fill="currentColor"
        d="M5 4v2h14V4H5zm0 10h4v6h6v-6h4l-7-7-7 7z"
      />
    </svg>
  );
}

function IconDelete() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden>
      <path
        fill="currentColor"
        d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"
      />
    </svg>
  );
}

function canPublishDoc(d: FolderLayerDoc) {
  return d.publish_status === "review" && Boolean(d.reviewed_at);
}

export function FolderBrowser({
  currentFolderId,
  layer,
  tree,
  busy,
  titleOverride,
  subtitleOverride,
  documentsOverride,
  emptyTextOverride,
  searchPlaceholder = "搜索文件名或上传人",
  hideCreateActions = false,
  hideSelectionActions = false,
  hideRowActions = false,
  selectionActionLabel,
  onSelectionAction,
  onCreateDoc,
  onCreateFolder,
  onOpenDoc,
  onRenameDoc,
  onDownloadDoc,
  onDeleteDoc,
  onDeleteDocs,
  onPublishDoc,
}: Props) {
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("create_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const currentFolder =
    tree.find((f) => f.folder_id === currentFolderId) ?? null;
  const documents = documentsOverride ?? layer?.documents ?? [];
  const atKnowledgeHome = documentsOverride == null && currentFolderId == null;

  useEffect(() => {
    setPage(1);
    setSelectedIds(new Set());
  }, [currentFolderId]);

  useEffect(() => {
    const alive = new Set(documents.map((d) => d.doc_id));
    setSelectedIds((prev) => {
      const next = new Set([...prev].filter((id) => alive.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [documents]);

  const filteredDocs = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    const base = keyword
      ? documents.filter((d) => {
          const name = (d.doc_name || "").toLowerCase();
          const uploader = (d.uploader || "").toLowerCase();
          return name.includes(keyword) || uploader.includes(keyword);
        })
      : documents;
    const sorted = [...base].sort((a, b) => {
      if (sortKey === "doc_name") {
        const av = (a.doc_name || "").localeCompare(b.doc_name || "", "zh-CN");
        return sortDirection === "asc" ? av : -av;
      }
      const at = a.create_at ? new Date(a.create_at).getTime() : 0;
      const bt = b.create_at ? new Date(b.create_at).getTime() : 0;
      return sortDirection === "asc" ? at - bt : bt - at;
    });
    return sorted;
  }, [documents, query, sortDirection, sortKey]);

  useEffect(() => {
    setPage(1);
  }, [query, sortKey, sortDirection]);

  const totalPages = Math.max(1, Math.ceil(filteredDocs.length / PAGE_SIZE));
  const pageSafe = Math.min(page, totalPages);
  const pageDocs = useMemo(() => {
    const start = (pageSafe - 1) * PAGE_SIZE;
    return filteredDocs.slice(start, start + PAGE_SIZE);
  }, [filteredDocs, pageSafe]);

  const pageIds = pageDocs.map((d) => d.doc_id);
  const allPageSelected =
    pageIds.length > 0 && pageIds.every((id) => selectedIds.has(id));
  const somePageSelected =
    pageIds.some((id) => selectedIds.has(id)) && !allPageSelected;

  function toggleOne(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAllPage() {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allPageSelected) {
        for (const id of pageIds) next.delete(id);
      } else {
        for (const id of pageIds) next.add(id);
      }
      return next;
    });
  }

  function selectedItems(): { id: string; name: string }[] {
    return documents
      .filter((d) => selectedIds.has(d.doc_id))
      .map((d) => ({
        id: d.doc_id,
        name: d.doc_name.trim() || "未命名文档",
      }));
  }

  function handleBulkDelete() {
    const items = selectedItems();
    if (items.length === 0) return;
    onDeleteDocs(items);
  }

  function handleSelectionAction() {
    const items = selectedItems();
    if (items.length === 0 || !onSelectionAction) return;
    onSelectionAction(items);
  }

  function toggleSort(nextKey: SortKey) {
    if (sortKey === nextKey) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(nextKey);
    setSortDirection(nextKey === "create_at" ? "desc" : "asc");
  }

  function sortIndicator(key: SortKey) {
    if (sortKey !== key) return "↕";
    return sortDirection === "asc" ? "↑" : "↓";
  }

  if (atKnowledgeHome) {
    return (
      <div className="chat-main doc-main kb-browser">
        <header className="kb-browser-header">
          <div>
            <h2 className="kb-browser-title">知识库</h2>
            <p className="kb-browser-empty" style={{ marginTop: "0.5rem" }}>
              请在左侧选择一个知识库，或创建新的知识库。
            </p>
          </div>
          <div className="kb-browser-actions">
            <button
              type="button"
              className="btn primary"
              disabled={busy}
              onClick={onCreateFolder}
            >
              创建知识库
            </button>
          </div>
        </header>
      </div>
    );
  }

  return (
    <div className="chat-main doc-main kb-browser">
      <header className="kb-browser-header">
        <div>
          <h2 className="kb-browser-title">
            {titleOverride ?? currentFolder?.name ?? "知识库"}
          </h2>
          <p className="kb-browser-subtitle">{subtitleOverride ?? "文件列表"}</p>
        </div>
        <div className="kb-browser-actions">
          <input
            type="search"
            className="kb-file-search"
            placeholder={searchPlaceholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label={searchPlaceholder}
          />
          {!hideSelectionActions && selectedIds.size > 0
            ? onSelectionAction && selectionActionLabel
              ? (
                <button
                  type="button"
                  className="btn primary"
                  disabled={busy}
                  onClick={handleSelectionAction}
                >
                  {selectionActionLabel}（{selectedIds.size}）
                </button>
              )
              : (
                <button
                  type="button"
                  className="btn"
                  disabled={busy}
                  onClick={handleBulkDelete}
                >
                  删除所选（{selectedIds.size}）
                </button>
              )
            : null}
          {!hideCreateActions ? (
            <button
              type="button"
              className="btn primary"
              disabled={busy}
              onClick={onCreateDoc}
            >
              + 新增文件
            </button>
          ) : null}
        </div>
      </header>

      <div className="kb-file-table-wrap">
        <table className="kb-file-table">
          <thead>
            <tr>
              <th className="kb-col-check">
                {hideSelectionActions ? null : (
                  <input
                    type="checkbox"
                    checked={allPageSelected}
                    ref={(el) => {
                      if (el) el.indeterminate = somePageSelected;
                    }}
                    onChange={toggleAllPage}
                    aria-label="全选本页"
                    disabled={pageDocs.length === 0}
                  />
                )}
              </th>
              <th>
                <button
                  type="button"
                  className="kb-sort-btn"
                  onClick={() => toggleSort("doc_name")}
                >
                  文件名 <span>{sortIndicator("doc_name")}</span>
                </button>
              </th>
              <th>
                <button
                  type="button"
                  className="kb-sort-btn"
                  onClick={() => toggleSort("create_at")}
                >
                  上传时间 <span>{sortIndicator("create_at")}</span>
                </button>
              </th>
              <th>状态</th>
              <th>上传人</th>
              <th>审核人</th>
              <th>审核时间</th>
              <th>审核意见</th>
              {hideRowActions ? null : <th className="kb-col-actions">操作</th>}
            </tr>
          </thead>
          <tbody>
            {pageDocs.map((d: FolderLayerDoc) => {
              const name = d.doc_name.trim() || "未命名文档";
              const checked = selectedIds.has(d.doc_id);
              return (
                <tr key={d.doc_id} className={checked ? "selected" : undefined}>
                  <td className="kb-col-check">
                    {hideSelectionActions ? null : (
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleOne(d.doc_id)}
                        aria-label={`选择 ${name}`}
                      />
                    )}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="kb-file-link"
                      onClick={() => onOpenDoc(d.doc_id)}
                    >
                      {name}
                    </button>
                  </td>
                  <td>{formatDate(d.create_at)}</td>
                  <td>{displayText(d.status_label)}</td>
                  <td>{displayText(d.uploader)}</td>
                  <td>{displayText(d.reviewer)}</td>
                  <td>{formatDate(d.reviewed_at ?? null)}</td>
                  <td>{displayText(d.review_comment)}</td>
                  {hideRowActions ? null : (
                    <td className="kb-col-actions">
                      <div className="kb-file-icon-actions">
                        {canPublishDoc(d) && onPublishDoc ? (
                          <button
                            type="button"
                            className="kb-icon-btn"
                            title="发布"
                            aria-label={`发布 ${name}`}
                            disabled={busy}
                            onClick={() => onPublishDoc(d.doc_id, name)}
                          >
                            <IconPublish />
                          </button>
                        ) : null}
                        <button
                          type="button"
                          className="kb-icon-btn"
                          title="重命名"
                          aria-label={`重命名 ${name}`}
                          disabled={busy}
                          onClick={() => onRenameDoc(d.doc_id, d.doc_name)}
                        >
                          <IconRename />
                        </button>
                        <button
                          type="button"
                          className="kb-icon-btn"
                          title="下载"
                          aria-label={`下载 ${name}`}
                          disabled={busy}
                          onClick={() => onDownloadDoc(d.doc_id, name)}
                        >
                          <IconDownload />
                        </button>
                        <button
                          type="button"
                          className="kb-icon-btn danger"
                          title="删除"
                          aria-label={`删除 ${name}`}
                          disabled={busy}
                          onClick={() => onDeleteDoc(d.doc_id, name)}
                        >
                          <IconDelete />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              );
            })}
            {filteredDocs.length === 0 ? (
              <tr>
                <td colSpan={hideRowActions ? 8 : 9} className="kb-file-empty">
                  {documents.length === 0
                    ? (emptyTextOverride ?? "暂无文件")
                    : "没有匹配结果"}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {filteredDocs.length > 0 ? (
        <div className="kb-pager">
          <span className="kb-pager-info">
            共 {filteredDocs.length} 个文件，第 {pageSafe}/{totalPages} 页
            {selectedIds.size > 0 ? ` · 已选 ${selectedIds.size}` : ""}
          </span>
          <div className="kb-pager-actions">
            <button
              type="button"
              className="btn"
              disabled={pageSafe <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              上一页
            </button>
            <button
              type="button"
              className="btn"
              disabled={pageSafe >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              下一页
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
