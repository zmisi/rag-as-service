"use client";

import { useEffect, useState } from "react";

import { DebugWorkspace } from "@/components/admin/DebugWorkspace";
import { backendUrl, resolveMainSiteUrl } from "@/lib/api";

export default function AdminDebugPage() {
  const [ready, setReady] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const me = await fetch(backendUrl("/api/v1/auth/me"), {
          credentials: "include",
          headers: { "X-Forwarded-Host": window.location.host },
        });
        if (me.status === 401 || me.status === 403) {
          window.location.href = resolveMainSiteUrl("/login");
          return;
        }
        if (!me.ok) {
          if (!cancelled) setError("无法验证登录状态");
          return;
        }

        const probe = await fetch("/backend/v1/admin/debug", {
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-Forwarded-Host": window.location.host,
          },
        });
        if (probe.status === 404) {
          if (!cancelled) setNotFound(true);
          return;
        }
        if (probe.status === 401 || probe.status === 403) {
          window.location.href = resolveMainSiteUrl("/login");
          return;
        }
        if (!probe.ok) {
          if (!cancelled) setError("无法加载 Debug 页");
          return;
        }
        if (!cancelled) setReady(true);
      } catch {
        if (!cancelled) setError("网络错误，请稍后重试");
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  if (notFound) {
    return (
      <main style={{ maxWidth: 480, margin: "2rem auto", padding: "0 1rem" }}>
        <h1>404</h1>
        <p>Not Found</p>
      </main>
    );
  }

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

  return <DebugWorkspace />;
}
