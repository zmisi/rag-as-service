"use client";

import { useEffect, useId, useState, type FormEvent } from "react";

import type { FolderVisibility } from "@/lib/api";

export type KnowledgeBaseFormValues = {
  name: string;
  description: string;
  visibility: FolderVisibility;
};

type Props = {
  open: boolean;
  busy?: boolean;
  title?: string;
  initial?: Partial<KnowledgeBaseFormValues>;
  onClose: () => void;
  onSubmit: (values: KnowledgeBaseFormValues) => void | Promise<void>;
};

const VISIBILITY_OPTIONS: {
  value: FolderVisibility;
  label: string;
  hint: string;
}[] = [
  {
    value: "public",
    label: "对所有人公开",
    hint: "租户内所有成员可见",
  },
  {
    value: "partial",
    label: "对部分人可见",
    hint: "仅指定成员可见（权限细则后续配置）",
  },
  {
    value: "private",
    label: "仅个人可见",
    hint: "仅创建者本人可见",
  },
];

export function CreateKnowledgeBaseModal({
  open,
  busy = false,
  title = "创建知识库",
  initial,
  onClose,
  onSubmit,
}: Props) {
  const formId = useId();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [visibility, setVisibility] = useState<FolderVisibility>("private");
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setName(initial?.name ?? "");
    setDescription(initial?.description ?? "");
    setVisibility(initial?.visibility ?? "private");
    setLocalError(null);
  }, [open, initial?.name, initial?.description, initial?.visibility]);

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
    const trimmed = name.trim();
    if (!trimmed) {
      setLocalError("请填写知识库名称");
      return;
    }
    setLocalError(null);
    await onSubmit({
      name: trimmed,
      description: description.trim(),
      visibility,
    });
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
            {title}
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
          <label className="kb-modal-field">
            <span className="kb-modal-label">
              知识库名称 <span className="kb-required">*</span>
            </span>
            <input
              type="text"
              value={name}
              maxLength={255}
              placeholder="例如：产品手册"
              disabled={busy}
              autoFocus
              onChange={(e) => setName(e.target.value)}
            />
          </label>

          <label className="kb-modal-field">
            <span className="kb-modal-label">描述</span>
            <textarea
              value={description}
              maxLength={2000}
              rows={3}
              placeholder="简要说明知识库用途（可选）"
              disabled={busy}
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>

          <fieldset className="kb-modal-field kb-modal-visibility">
            <legend className="kb-modal-label">可见范围</legend>
            <div className="kb-visibility-options">
              {VISIBILITY_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className={`kb-visibility-option${visibility === opt.value ? " selected" : ""}`}
                >
                  <input
                    type="radio"
                    name={`${formId}-visibility`}
                    value={opt.value}
                    checked={visibility === opt.value}
                    disabled={busy}
                    onChange={() => setVisibility(opt.value)}
                  />
                  <span className="kb-visibility-text">
                    <span className="kb-visibility-title">{opt.label}</span>
                    <span className="kb-visibility-hint">{opt.hint}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

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
              {busy ? "创建中…" : "创建"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
