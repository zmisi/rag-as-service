"use client";

import { FormEvent, useState } from "react";

import { backendUrl } from "@/lib/api";

type FormState = {
  email: string;
  password: string;
  subdomain: string;
};

const initialState: FormState = {
  email: "",
  password: "",
  subdomain: "",
};

export function RegisterForm() {
  const [form, setForm] = useState<FormState>(initialState);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (form.password.length < 8) {
      setError("密码至少 8 个字符");
      return;
    }
    if (form.subdomain.length < 3) {
      setError("子域至少 3 个字符");
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch(
        backendUrl("/api/v1/auth/register?redirect=1"),
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/html",
          },
          credentials: "include",
          redirect: "manual",
          body: JSON.stringify(form),
        },
      );

      if (response.status === 302) {
        const location = response.headers.get("Location");
        if (location) {
          window.location.href = location;
          return;
        }
      }

      if (response.status === 201) {
        const body = (await response.json()) as { redirect_url?: string };
        if (body.redirect_url) {
          window.location.href = body.redirect_url;
          return;
        }
      }

      const payload = (await response.json().catch(() => null)) as
        | { detail?: { message?: string; code?: string } }
        | null;
      const message =
        payload?.detail?.message ??
        (response.status === 409
          ? "邮箱或子域已被占用"
          : "注册失败，请检查输入");
      setError(message);
    } catch {
      setError("网络错误，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} style={{ display: "grid", gap: "1rem" }}>
      <h1>注册</h1>
      <p>创建账号并选定租户子域（注册后不可修改）。</p>

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
          minLength={8}
          value={form.password}
          onChange={(event) =>
            setForm((current) => ({ ...current, password: event.target.value }))
          }
        />
      </label>

      <label style={{ display: "grid", gap: "0.25rem" }}>
        子域（subdomain）
        <input
          type="text"
          required
          minLength={3}
          maxLength={32}
          pattern="[A-Za-z0-9-]+"
          value={form.subdomain}
          onChange={(event) =>
            setForm((current) => ({
              ...current,
              subdomain: event.target.value,
            }))
          }
        />
      </label>

      {error ? (
        <p role="alert" style={{ color: "#b00020" }}>
          {error}
        </p>
      ) : null}

      <button type="submit" disabled={submitting}>
        {submitting ? "注册中…" : "注册"}
      </button>
    </form>
  );
}
