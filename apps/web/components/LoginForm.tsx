"use client";

import { FormEvent, useState } from "react";

import { backendUrl, resolvePostRegistrationUrl } from "@/lib/api";

type FormState = {
  email: string;
  password: string;
};

const initialState: FormState = {
  email: "",
  password: "",
};

export function LoginForm() {
  const [form, setForm] = useState<FormState>(initialState);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const response = await fetch(backendUrl("/api/v1/auth/login"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          // Next rewrite → api:8000 会改写 Host；后端用此头校验主站
          "X-Forwarded-Host": window.location.host,
        },
        credentials: "include",
        body: JSON.stringify(form),
      });

      if (response.status === 200) {
        const body = (await response.json()) as { redirect_url?: string };
        if (body.redirect_url) {
          window.location.href = resolvePostRegistrationUrl(body.redirect_url);
          return;
        }
      }

      const payload = (await response.json().catch(() => null)) as
        | { detail?: { message?: string } }
        | null;
      setError(payload?.detail?.message ?? "邮箱或密码错误");
    } catch {
      setError("网络错误，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} style={{ display: "grid", gap: "1rem" }}>
      <h1>登录</h1>
      <p>使用 Email 登录您的租户工作区。</p>

      <label style={{ display: "grid", gap: "0.25rem" }}>
        Email
        <input
          type="email"
          required
          value={form.email}
          onChange={(event) =>
            setForm((current) => ({ ...current, email: event.target.value }))
          }
        />
      </label>

      <label style={{ display: "grid", gap: "0.25rem" }}>
        密码
        <input
          type="password"
          required
          value={form.password}
          onChange={(event) =>
            setForm((current) => ({ ...current, password: event.target.value }))
          }
        />
      </label>

      {error ? (
        <p role="alert" style={{ color: "#b00020" }}>
          {error}
        </p>
      ) : null}

      <button type="submit" className="btn primary" disabled={submitting}>
        {submitting ? "登录中…" : "登录"}
      </button>
    </form>
  );
}
