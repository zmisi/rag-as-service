"use client";

import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { backendUrl, changePassword, resolveMainSiteUrl, resolvePostRegistrationUrl } from "@/lib/api";

export default function ChangePasswordPage() {
  const searchParams = useSearchParams();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const nextUrl = searchParams.get("next") || "/";

  useEffect(() => {
    let cancelled = false;

    async function checkSession() {
      try {
        const response = await fetch(backendUrl("/api/v1/auth/me"), {
          credentials: "include",
        });
        if (response.status === 401 || response.status === 403) {
          window.location.href = resolveMainSiteUrl("/login");
          return;
        }
        if (!response.ok || cancelled) return;
        const body = (await response.json()) as { must_change_password?: boolean };
        if (!body.must_change_password) {
          window.location.href = resolvePostRegistrationUrl(nextUrl);
        }
      } catch {
        /* keep page interactive */
      }
    }

    void checkSession();
    return () => {
      cancelled = true;
    };
  }, [nextUrl]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("新密码至少 8 位");
      return;
    }
    if (password !== confirmPassword) {
      setError("两次输入的新密码不一致");
      return;
    }
    setSubmitting(true);
    try {
      await changePassword(password);
      window.location.href = resolvePostRegistrationUrl(nextUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "修改密码失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} style={{ display: "grid", gap: "1rem" }}>
      <h1>首次登录请修改密码</h1>
      <p>系统已为您分配临时密码，继续使用前需要先设置新的登录密码。</p>

      <label style={{ display: "grid", gap: "0.25rem" }}>
        新密码
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </label>

      <label style={{ display: "grid", gap: "0.25rem" }}>
        确认新密码
        <input
          type="password"
          required
          minLength={8}
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
        />
      </label>

      {error ? (
        <p role="alert" style={{ color: "#b00020" }}>
          {error}
        </p>
      ) : null}

      <button type="submit" className="btn primary" disabled={submitting}>
        {submitting ? "提交中…" : "确认修改"}
      </button>
    </form>
  );
}
