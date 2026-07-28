"use client";

import { useEffect, useId, useState, type FormEvent } from "react";

import type { TenantMemberRole } from "@/lib/api";

export type AddMemberValues = {
  member_name: string;
  email: string;
  role: Exclude<TenantMemberRole, "owner">;
};

type Props = {
  open: boolean;
  busy?: boolean;
  onClose: () => void;
  onSubmit: (values: AddMemberValues) => void | Promise<void>;
};

export function AddMemberModal({ open, busy = false, onClose, onSubmit }: Props) {
  const formId = useId();
  const [memberName, setMemberName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Exclude<TenantMemberRole, "owner">>("member");
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setMemberName("");
    setEmail("");
    setRole("member");
    setLocalError(null);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !busy) onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, busy, onClose]);

  if (!open) return null;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmedName = memberName.trim();
    const trimmedEmail = email.trim();
    if (!trimmedName) {
      setLocalError("请填写成员名");
      return;
    }
    if (!trimmedEmail) {
      setLocalError("请填写邮箱");
      return;
    }
    setLocalError(null);
    await onSubmit({
      member_name: trimmedName,
      email: trimmedEmail,
      role,
    });
  }

  return (
    <div
      className="kb-modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <div className="kb-modal" role="dialog" aria-modal="true" aria-labelledby={`${formId}-title`}>
        <header className="kb-modal-header">
          <h2 id={`${formId}-title`} className="kb-modal-title">
            添加成员
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

        <form className="kb-modal-form" onSubmit={(event) => void handleSubmit(event)}>
          <label className="kb-modal-field">
            <span className="kb-modal-label">成员名</span>
            <input
              type="text"
              value={memberName}
              maxLength={64}
              disabled={busy}
              autoFocus
              onChange={(event) => setMemberName(event.target.value)}
            />
          </label>

          <label className="kb-modal-field">
            <span className="kb-modal-label">邮箱</span>
            <input
              type="email"
              value={email}
              disabled={busy}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>

          <label className="kb-modal-field">
            <span className="kb-modal-label">角色</span>
            <select
              value={role}
              disabled={busy}
              onChange={(event) =>
                setRole(event.target.value as Exclude<TenantMemberRole, "owner">)
              }
            >
              <option value="member">普通用户</option>
              <option value="admin">管理员</option>
            </select>
          </label>

          {localError ? (
            <p className="kb-modal-error" role="alert">
              {localError}
            </p>
          ) : null}

          <footer className="kb-modal-footer">
            <button type="button" className="btn" disabled={busy} onClick={onClose}>
              取消
            </button>
            <button type="submit" className="btn primary" disabled={busy}>
              {busy ? "提交中…" : "添加成员"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
