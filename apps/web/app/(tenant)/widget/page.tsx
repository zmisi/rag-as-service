"use client";

import { useEffect, useState } from "react";

import { DraftHero } from "@/components/chat/DraftHero";
import {
  createWidgetSiteKey,
  listWidgetSiteKeys,
  resolveMainSiteUrl,
  updateWidgetSiteKey,
} from "@/lib/api";

type Status = "loading" | "ready" | "need_login" | "error";

/**
 * F12 harness: customer-site simulation. Visual matches Portal empty hero;
 * float widget.js stays independent in the corner.
 */
export default function WidgetHarnessPage() {
  const [siteKey, setSiteKey] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function resolveKey() {
      const fromEnv = process.env.NEXT_PUBLIC_WIDGET_SITE_KEY?.trim();
      if (fromEnv && fromEnv !== "pk_PLACEHOLDER") {
        if (!cancelled) {
          setSiteKey(fromEnv);
          setStatus("ready");
        }
        return;
      }

      const origin = window.location.origin;
      try {
        const keys = await listWidgetSiteKeys();
        if (cancelled) return;

        const active = keys.filter((k) => k.status === "active");
        let chosen = active.find((k) => k.allowed_origins.includes(origin));

        if (!chosen && active.length > 0) {
          chosen = active[0];
          const origins = Array.from(
            new Set([...chosen.allowed_origins, origin]),
          );
          chosen = await updateWidgetSiteKey(chosen.id, {
            allowed_origins: origins,
          });
        }

        if (!chosen) {
          chosen = await createWidgetSiteKey({
            allowed_origins: [origin],
            name: "dev-harness",
          });
        }

        if (!cancelled) {
          setSiteKey(chosen.public_key);
          setStatus("ready");
        }
      } catch (e) {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : "无法获取 site key";
        if (msg.startsWith("401") || msg.startsWith("403")) {
          setStatus("need_login");
          setError(null);
        } else {
          setStatus("error");
          setError(msg);
        }
      }
    }

    void resolveKey();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!siteKey) return;

    const existing = document.querySelector(
      'script[src="/widget.js"][data-lxzxai-harness="1"]',
    );
    if (existing) {
      existing.setAttribute("data-site-key", siteKey);
      return;
    }

    const s = document.createElement("script");
    s.src = "/widget.js";
    s.async = true;
    s.setAttribute("data-site-key", siteKey);
    s.setAttribute("data-welcome", "你好，我是知识库助手，有什么可以帮你？");
    s.setAttribute("data-theme-color", "#20b898");
    s.setAttribute("data-lxzxai-harness", "1");
    document.body.appendChild(s);
    return () => {
      s.remove();
      document.getElementById("lxzxai-widget-root")?.remove();
    };
  }, [siteKey]);

  return (
    <main className="widget-harness" data-testid="widget-harness">
      <div className="widget-harness-stage">
        <DraftHero />
        {status === "need_login" ? (
          <p className="widget-harness-status" role="alert">
            请先{" "}
            <a href={resolveMainSiteUrl("/login")}>登录</a>
            {" "}以启用右下角助手。
          </p>
        ) : null}
        {status === "error" && error ? (
          <p className="widget-harness-status" role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </main>
  );
}
