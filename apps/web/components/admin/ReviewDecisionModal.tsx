"use client";

import { useEffect, useId, useState, type FormEvent } from "react";

export type ReviewDecision = "approve" | "reject";

export type ReviewDecisionValues = {
  decision: ReviewDecision;
  reviewComment: string;
};

type Props = {
  open: boolean;
  busy?: boolean;
  fileName: string;
  onClose: () => void;
  onSubmit: (values: ReviewDecisionValues) => void | Promise<void>;
};

export function ReviewDecisionModal({
  open,
  busy = false,
  fileName,
  onClose,
  onSubmit,
}: Props) {
  const formId = useId();
  const [decision, setDecision] = useState<ReviewDecision>("approve");
  const [reviewComment, setReviewComment] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setDecision("approve");
    setReviewComment("");
    setLocalError(null);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && !busy) onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, busy, onClose]);

  if (!open) return null;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const comment = reviewComment.trim();
    if (decision === "reject" && !comment) {
      setLocalError("审核不通过时请填写审核意见");
      return;
    }
    setLocalError(null);
    await onSubmit({ decision, reviewComment: comment });
  }

  return (
    <div
      className="kb-modal-backdrop"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !busy) onClose();
      }}
    >
      <div
        className="kb-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${formId}-title`}
      >
        <header className="kb-modal-header">
          <h2 id={`${formId}-title`} className="kb-modal-title">
            审核
          </h2>
          <button
            type="button"
            className="kb-modal-close"
            aria-label="关闭"
            disabled={busy}
            onClick={onClose}
          >
            ×
          </button>
        </header>

        <form className="kb-modal-form" onSubmit={(e) => void handleSubmit(e)}>
          <p className="kb-browser-subtitle" style={{ margin: "0 0 0.25rem" }}>
            文件：<strong>{fileName}</strong>
          </p>

          <fieldset className="kb-modal-field kb-modal-visibility">
            <legend className="kb-modal-label">
              审核结果 <span className="kb-required">*</span>
            </legend>
            <div className="kb-visibility-options">
              <label
                className={`kb-visibility-option${decision === "approve" ? " selected" : ""}`}
              >
                <input
                  type="radio"
                  name={`${formId}-decision`}
                  checked={decision === "approve"}
                  disabled={busy}
                  onChange={() => setDecision("approve")}
                />
                <span className="kb-visibility-text">
                  <span className="kb-visibility-title">审核通过</span>
                  <span className="kb-visibility-hint">
                    通过后状态变为待发布，可在知识库文件列表中点击发布
                  </span>
                </span>
              </label>
              <label
                className={`kb-visibility-option${decision === "reject" ? " selected" : ""}`}
              >
                <input
                  type="radio"
                  name={`${formId}-decision`}
                  checked={decision === "reject"}
                  disabled={busy}
                  onChange={() => setDecision("reject")}
                />
                <span className="kb-visibility-text">
                  <span className="kb-visibility-title">审核不通过</span>
                  <span className="kb-visibility-hint">
                    退回为草稿，上传人可修改后再次提交
                  </span>
                </span>
              </label>
            </div>
          </fieldset>

          <label className="kb-modal-field">
            <span className="kb-modal-label">
              审核意见
              {decision === "reject" ? (
                <span className="kb-required"> *</span>
              ) : null}
            </span>
            <textarea
              rows={4}
              value={reviewComment}
              disabled={busy}
              placeholder={
                decision === "reject"
                  ? "请说明不通过原因"
                  : "可选，填写给上传人的意见"
              }
              onChange={(e) => setReviewComment(e.target.value)}
            />
          </label>

          {localError ? (
            <p className="kb-modal-error" role="alert">
              {localError}
            </p>
          ) : null}

          <footer className="kb-modal-footer">
            <button
              type="button"
              className="btn"
              disabled={busy}
              onClick={onClose}
            >
              取消
            </button>
            <button type="submit" className="btn primary" disabled={busy}>
              {busy ? "提交中…" : "提交审核"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
