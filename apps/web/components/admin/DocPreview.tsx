"use client";

import { useEffect, useState } from "react";

import { fetchDocumentPreview } from "@/lib/api";

type Props = {
  documentId: string;
  fileName?: string | null;
};

export function DocPreview({ documentId, fileName }: Props) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [textContent, setTextContent] = useState<string | null>(null);
  const [kind, setKind] = useState<"pdf" | "html" | "text" | "other">("other");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    async function load() {
      setLoading(true);
      setError(null);
      setBlobUrl(null);
      setTextContent(null);
      try {
        const preview = await fetchDocumentPreview(documentId);
        if (cancelled) {
          URL.revokeObjectURL(preview.blobUrl);
          return;
        }
        if (preview.kind === "text") {
          const text = await fetch(preview.blobUrl).then((r) => r.text());
          URL.revokeObjectURL(preview.blobUrl);
          if (cancelled) return;
          setKind("text");
          setTextContent(text);
        } else {
          objectUrl = preview.blobUrl;
          setKind(preview.kind);
          setBlobUrl(preview.blobUrl);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "预览失败");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId]);

  if (loading) {
    return (
      <div className="doc-preview-panel">
        <p className="kb-browser-empty">正在加载预览…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="doc-preview-panel">
        <p className="doc-alert" role="alert">
          {error}
        </p>
      </div>
    );
  }

  const title = fileName?.trim() || "文档预览";

  if (kind === "text") {
    return (
      <div className="doc-preview-panel doc-preview-text">
        <pre className="doc-preview-pre">{textContent ?? ""}</pre>
      </div>
    );
  }

  if (!blobUrl) {
    return (
      <div className="doc-preview-panel">
        <p className="kb-browser-empty">暂无可预览内容</p>
      </div>
    );
  }

  return (
    <div className="doc-preview-panel">
      <iframe className="doc-preview-frame" title={title} src={blobUrl} />
    </div>
  );
}
