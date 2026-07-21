"use client";

import {
  STATUS_LABELS,
  TAG_TABS,
  type DocSummary,
  type DocTag,
  tagLabel,
} from "@/lib/documents";

type Props = {
  documents: DocSummary[];
  tagFilter: DocTag | "all";
  search: string;
  selectedId: string | null;
  busy: boolean;
  onTagFilter: (tag: DocTag | "all") => void;
  onSearch: (q: string) => void;
  onSelect: (id: string) => void;
  onCreate: () => void;
};

export function DocSidebar({
  documents,
  tagFilter,
  search,
  selectedId,
  busy,
  onTagFilter,
  onSearch,
  onSelect,
  onCreate,
}: Props) {
  const q = search.trim().toLowerCase();
  const filtered = documents.filter((d) => {
    if (tagFilter !== "all" && d.tag !== tagFilter) return false;
    if (q && !d.title.toLowerCase().includes(q)) return false;
    return true;
  });

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1 className="sidebar-title">知识库</h1>
        <button
          type="button"
          className="btn primary"
          disabled={busy}
          onClick={onCreate}
        >
          新建文档
        </button>
      </div>

      <input
        className="doc-search"
        type="search"
        placeholder="搜索标题…"
        value={search}
        onChange={(e) => onSearch(e.target.value)}
        aria-label="搜索文档标题"
      />

      <div className="tabs doc-tag-tabs" role="tablist">
        {TAG_TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            role="tab"
            className={`tab${tagFilter === tab.value ? " active" : ""}`}
            aria-selected={tagFilter === tab.value}
            onClick={() => onTagFilter(tab.value)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <ul className="doc-list">
        {filtered.length === 0 ? (
          <li className="doc-list-empty">暂无文档</li>
        ) : (
          filtered.map((doc) => (
            <li key={doc.id}>
              <button
                type="button"
                className={`doc-list-item${selectedId === doc.id ? " selected" : ""}`}
                onClick={() => onSelect(doc.id)}
              >
                <span className="doc-list-title">
                  {doc.title.trim() || "未命名文档"}
                </span>
                <span className="doc-list-meta">
                  <span className={`badge status-${doc.status}`}>
                    {STATUS_LABELS[doc.status]}
                  </span>
                  {doc.version !== "0.0" ? (
                    <span className="doc-version">v{doc.version}</span>
                  ) : null}
                </span>
                {doc.tag ? (
                  <span className="doc-list-tag">{tagLabel(doc.tag)}</span>
                ) : null}
              </button>
            </li>
          ))
        )}
      </ul>
    </aside>
  );
}
