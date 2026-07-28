"use client";

import { useEffect, useState } from "react";

import { WidgetAdminWorkspace } from "@/components/admin/WidgetAdminWorkspace";
import { backendUrl, resolveMainSiteUrl } from "@/lib/api";

export default function AdminWidgetPage() {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function checkAuth() {
      try {
        const response = await fetch(backendUrl("/api/v1/auth/me"), {
          credentials: "include",
          headers: {
            "X-Forwarded-Host": window.location.host,
          },
        });
        if (response.status === 401 || response.status === 403) {
          window.location.href = resolveMainSiteUrl("/login");
          return;
        }
        if (!response.ok) {
          if (!cancelled) setError("无法验证登录状态");
          return;
        }
        const body = (await response.json()) as {
          must_change_password?: boolean;
        };
        if (body.must_change_password) {
          window.location.href = resolveMainSiteUrl(
            `/change-password?next=${encodeURIComponent(window.location.href)}`,
          );
          return;
        }
        if (!cancelled) setReady(true);
      } catch {
        if (!cancelled) setError("网络错误，请稍后重试");
      }
    }

    void checkAuth();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <main style={{ maxWidth: 480, margin: "2rem auto", padding: "0 1rem" }}>
        <p role="alert" style={{ color: "#b00020" }}>
          {error}
        </p>
      </main>
    );
  }

  if (!ready) {
    return (
      <main style={{ maxWidth: 480, margin: "2rem auto", padding: "0 1rem" }}>
        <p>验证登录中…</p>
      </main>
    );
  }

  return <WidgetAdminWorkspace />;
}
