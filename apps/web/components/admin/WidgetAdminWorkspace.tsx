"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import {
  createWidgetSiteKey,
  getWidgetSnippet,
  listWidgetSiteKeys,
  revokeWidgetSiteKey,
  updateWidgetSiteKey,
  type WidgetSiteKey,
} from "@/lib/api";

export function WidgetAdminWorkspace() {
  const [keys, setKeys] = useState<WidgetSiteKey[]>([]);
  const [originsText, setOriginsText] = useState(
    "http://tenant-a.lxzxai.com:3000",
  );
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [snippet, setSnippet] = useState<string | null>(null);
  const [editOrigins, setEditOrigins] = useState<Record<string, string>>({});

  const refresh = useCallback(async () => {
    const items = await listWidgetSiteKeys();
    setKeys(items);
    const map: Record<string, string> = {};
    for (const k of items) {
      map[k.id] = k.allowed_origins.join("\n");
    }
    setEditOrigins(map);
  }, []);

  useEffect(() => {
    void refresh().catch((e) =>
      setError(e instanceof Error ? e.message : "加载失败"),
    );
  }, [refresh]);

  async function onCreate() {
    setBusy(true);
    setError(null);
    setSnippet(null);
    try {
      const origins = originsText
        .split(/[\n,]/)
        .map((s) => s.trim())
        .filter(Boolean);
      const row = await createWidgetSiteKey({
        allowed_origins: origins,
        name: name.trim() || undefined,
      });
      const sn = await getWidgetSnippet(row.id);
      setSnippet(sn.snippet);
      setName("");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function onSaveOrigins(id: string) {
    setBusy(true);
    setError(null);
    try {
      const origins = (editOrigins[id] ?? "")
        .split(/[\n,]/)
        .map((s) => s.trim())
        .filter(Boolean);
      await updateWidgetSiteKey(id, { allowed_origins: origins });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function onRevoke(id: string) {
    setBusy(true);
    setError(null);
    try {
      await revokeWidgetSiteKey(id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "吊销失败");
    } finally {
      setBusy(false);
    }
  }

  async function onCopySnippet(id: string) {
    setBusy(true);
    setError(null);
    try {
      const sn = await getWidgetSnippet(id);
      setSnippet(sn.snippet);
      await navigator.clipboard.writeText(sn.snippet);
    } catch (e) {
      setError(e instanceof Error ? e.message : "复制失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="widget-admin">
      <header className="widget-admin-header">
        <div>
          <p className="widget-admin-nav">
            <Link href="/admin">知识库</Link>
            <span aria-hidden> / </span>
            <Link href="/admin/debug">Debug</Link>
            <span aria-hidden> / </span>
            <span>Embed Widget</span>
          </p>
          <h1>Embed Widget Site Keys</h1>
          <p className="widget-admin-lead">
            生成公开 site key（pk_…）与 Origin 白名单。浏览器只持 pk_，不要放入服务端
            API Key。
          </p>
        </div>
        <Link className="btn" href="/widget">
          打开测试页
        </Link>
      </header>

      {error ? (
        <p role="alert" className="widget-admin-error">
          {error}
        </p>
      ) : null}

      <section className="widget-admin-card">
        <h2>新建 Site Key</h2>
        <label className="widget-admin-label">
          名称（可选）
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="官网 / App"
            disabled={busy}
          />
        </label>
        <label className="widget-admin-label">
          允许 Origin（每行一个，精确 scheme+host[:port]）
          <textarea
            rows={4}
            value={originsText}
            onChange={(e) => setOriginsText(e.target.value)}
            disabled={busy}
          />
        </label>
        <button
          type="button"
          className="btn primary"
          disabled={busy}
          onClick={() => void onCreate()}
        >
          创建
        </button>
      </section>

      {snippet ? (
        <section className="widget-admin-card">
          <h2>Snippet</h2>
          <pre className="widget-admin-snippet">{snippet}</pre>
        </section>
      ) : null}

      <section className="widget-admin-card">
        <h2>已有 Keys</h2>
        {keys.length === 0 ? (
          <p className="muted">暂无 site key</p>
        ) : (
          <ul className="widget-admin-list">
            {keys.map((k) => (
              <li key={k.id} className="widget-admin-item">
                <div className="widget-admin-item-head">
                  <code>{k.public_key}</code>
                  <span className={`badge status-${k.status}`}>{k.status}</span>
                  {k.name ? <span className="muted">{k.name}</span> : null}
                </div>
                <label className="widget-admin-label">
                  Origins
                  <textarea
                    rows={3}
                    value={editOrigins[k.id] ?? ""}
                    disabled={busy || k.status === "revoked"}
                    onChange={(e) =>
                      setEditOrigins((prev) => ({
                        ...prev,
                        [k.id]: e.target.value,
                      }))
                    }
                  />
                </label>
                <div className="widget-admin-actions">
                  <button
                    type="button"
                    className="btn"
                    disabled={busy || k.status === "revoked"}
                    onClick={() => void onSaveOrigins(k.id)}
                  >
                    保存 Origins
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={busy}
                    onClick={() => void onCopySnippet(k.id)}
                  >
                    复制 Snippet
                  </button>
                  <button
                    type="button"
                    className="btn danger"
                    disabled={busy || k.status === "revoked"}
                    onClick={() => void onRevoke(k.id)}
                  >
                    吊销
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
