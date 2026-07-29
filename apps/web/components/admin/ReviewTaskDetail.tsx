"use client";

import { useState } from "react";

import { DocPreview } from "@/components/admin/DocPreview";
import {
  ReviewDecisionModal,
  type ReviewDecisionValues,
} from "@/components/admin/ReviewDecisionModal";
import {
  formatBytes,
  formatVersionDisplay,
  tagLabel,
  type DocDetail,
} from "@/lib/documents";

type Props = {
  doc: DocDetail;
  uploader?: string | null;
  reviewer?: string | null;
  reviewedAt?: string | null;
  reviewComment?: string | null;
  busy: boolean;
  onBack: () => void;
  onCompleteReview: (values: ReviewDecisionValues) => void | Promise<void>;
};

function formatDate(value?: string | null) {
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

export function ReviewTaskDetail({
  doc,
  uploader,
  reviewer,
  reviewedAt,
  reviewComment,
  busy,
  onBack,
  onCompleteReview,
}: Props) {
  const [modalOpen, setModalOpen] = useState(false);
  const fileName = doc.file_name?.trim() || doc.title.trim() || "未命名文档";

  return (
    <div className="chat-main doc-main kb-browser">
      <header className="kb-browser-header">
        <div>
          <button type="button" className="kb-crumb" onClick={onBack}>
            ← 返回待审核任务
          </button>
          <h2 className="kb-browser-title" style={{ marginTop: "0.65rem" }}>
            {fileName}
          </h2>
          <p className="kb-browser-subtitle">文件详情与预览</p>
        </div>
        <div className="kb-browser-actions">
          {doc.status === "review" ? (
            <button
              type="button"
              className="btn primary"
              disabled={busy}
              onClick={() => setModalOpen(true)}
            >
              审核
            </button>
          ) : null}
        </div>
      </header>

      <dl className="doc-meta-grid">
        <div>
          <dt>文件大小</dt>
          <dd>{formatBytes(doc.file_size_bytes ?? 0)}</dd>
        </div>
        <div>
          <dt>上传时间</dt>
          <dd>{formatDate(doc.create_at)}</dd>
        </div>
        <div>
          <dt>状态</dt>
          <dd>{doc.status === "review" ? "待审核" : doc.status}</dd>
        </div>
        <div>
          <dt>文档分类</dt>
          <dd>{doc.tag ? tagLabel(doc.tag) : "-"}</dd>
        </div>
        <div>
          <dt>上传人</dt>
          <dd>{uploader?.trim() || "-"}</dd>
        </div>
        <div>
          <dt>审核人</dt>
          <dd>{reviewer?.trim() || "-"}</dd>
        </div>
        <div>
          <dt>审核时间</dt>
          <dd>{formatDate(reviewedAt)}</dd>
        </div>
        <div>
          <dt>当前版本</dt>
          <dd>{formatVersionDisplay(doc.version)}</dd>
        </div>
        <div className="doc-meta-span">
          <dt>审核意见</dt>
          <dd>{reviewComment?.trim() || "-"}</dd>
        </div>
      </dl>

      <section className="doc-preview-section">
        <h3 className="doc-preview-heading">文件预览</h3>
        <DocPreview documentId={doc.id} fileName={doc.file_name} />
      </section>

      <ReviewDecisionModal
        open={modalOpen}
        busy={busy}
        fileName={fileName}
        onClose={() => {
          if (!busy) setModalOpen(false);
        }}
        onSubmit={async (values) => {
          await onCompleteReview(values);
          setModalOpen(false);
        }}
      />
    </div>
  );
}
