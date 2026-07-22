"use client";

import { useRef } from "react";

import { DocStatusStepper } from "@/components/admin/DocStatusStepper";
import { IndexJobStatusCard } from "@/components/admin/IndexJobStatusCard";
import {
  TAG_OPTIONS,
  formatBytes,
  isAllowedFile,
  MAX_FILE_BYTES,
  tagLabel,
  type DocDetail,
  type DocTag,
  type IndexJobStatus,
} from "@/lib/documents";

type Props = {
  doc: DocDetail | null;
  title: string;
  tag: string;
  validationErrors: string[];
  busy: boolean;
  indexJob: IndexJobStatus | null;
  onTitleChange: (v: string) => void;
  onTagChange: (v: string) => void;
  onSave: () => void;
  onSubmitReview: () => void;
  onPublish: () => void;
  onNewVersion: () => void;
  onUploadFiles: (files: FileList) => void;
};

export function DocEditor({
  doc,
  title,
  tag,
  validationErrors,
  busy,
  indexJob,
  onTitleChange,
  onTagChange,
  onSave,
  onSubmitReview,
  onPublish,
  onNewVersion,
  onUploadFiles,
}: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const readOnly = doc?.status === "review" || doc?.status === "published";

  if (!doc) {
    return (
      <div className="chat-main doc-main-empty">
        <p>选择或新建文档</p>
      </div>
    );
  }

  function handleFilePick() {
    fileRef.current?.click();
  }

  function handlePublishClick() {
    if (!doc) return;
    const msg = [
      "确认发布文档？",
      "",
      `标题：${title.trim() || doc.title}`,
      `分类：${tag ? tagLabel(tag) : "—"}`,
      `版本：${doc.version === "0.0" ? "1.0（首版）" : doc.version}`,
      `文件：${doc.files.length} 个`,
      "",
      "发布后将建立知识库索引，供 AI 问答检索。",
    ].join("\n");
    if (window.confirm(msg)) {
      onPublish();
    }
  }

  return (
    <div className="chat-main doc-main">
      <header className="doc-main-header">
        <h2>{title.trim() || doc.title.trim() || "未命名文档"}</h2>
      </header>

      <DocStatusStepper status={doc.status} />

      <section className="doc-form">
        <div className="doc-field">
          <label htmlFor="doc-title">文档标题</label>
          <input
            id="doc-title"
            type="text"
            placeholder="例如：产品使用手册 v2.0"
            value={title}
            disabled={readOnly || busy}
            onChange={(e) => onTitleChange(e.target.value)}
          />
        </div>

        <div className="doc-field">
          <label htmlFor="doc-tag">文档分类</label>
          <select
            id="doc-tag"
            value={tag}
            disabled={readOnly || busy}
            onChange={(e) => onTagChange(e.target.value)}
          >
            <option value="">请选择…</option>
            {TAG_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label} — {opt.description}
              </option>
            ))}
          </select>
        </div>

        <div className="doc-field">
          <span className="doc-field-label">源文件</span>
          {!readOnly ? (
            <>
              <input
                ref={fileRef}
                type="file"
                multiple
                className="doc-file-input"
                accept=".txt,.md,.pdf,.doc,.docx,.ppt,.pptx"
                onChange={(e) => {
                  if (e.target.files?.length) {
                    onUploadFiles(e.target.files);
                    e.target.value = "";
                  }
                }}
              />
              <button
                type="button"
                className="btn"
                disabled={busy}
                onClick={handleFilePick}
              >
                选择文件
              </button>
              <p className="doc-hint">
                支持 txt / pdf / word / ppt，单文件 ≤ 20MB
              </p>
            </>
          ) : null}
          <ul className="doc-file-list">
            {doc.files.map((f) => (
              <li key={f.id}>
                <span>{f.filename}</span>
                <span className="muted">
                  {formatBytes(f.size_bytes)}
                </span>
              </li>
            ))}
          </ul>
        </div>

        {validationErrors.length > 0 ? (
          <ul className="doc-validation" role="alert">
            {validationErrors.map((err) => (
              <li key={err}>{err}</li>
            ))}
          </ul>
        ) : null}
      </section>

      <div className="doc-actions">
        {doc.status === "draft" ? (
          <>
            <button
              type="button"
              className="btn"
              disabled={busy}
              onClick={onSave}
            >
              {busy ? "保存中…" : "保存草稿"}
            </button>
            <button
              type="button"
              className="btn primary"
              disabled={busy}
              onClick={onSubmitReview}
            >
              {busy ? "提交中…" : "提交审核"}
            </button>
          </>
        ) : null}
        {doc.status === "review" ? (
          <button
            type="button"
            className="btn primary"
            disabled={busy}
            onClick={handlePublishClick}
          >
            {busy ? "发布中…" : "发布"}
          </button>
        ) : null}
        {doc.status === "published" ? (
          <button
            type="button"
            className="btn primary"
            disabled={busy}
            onClick={onNewVersion}
          >
            {busy ? "处理中…" : "编辑新版本"}
          </button>
        ) : null}
      </div>

      {doc.version !== "0.0" ? (
        <p className="doc-version-line">当前版本：v{doc.version}</p>
      ) : null}

      <IndexJobStatusCard
        job={indexJob}
        published={doc.status === "published"}
      />
    </div>
  );
}
