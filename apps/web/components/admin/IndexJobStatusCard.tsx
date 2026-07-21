"use client";

import type { IndexJobStatus } from "@/lib/documents";

const LABELS: Record<IndexJobStatus["status"], string> = {
  pending: "索引排队中…",
  running: "索引进行中…",
  succeeded: "索引成功",
  failed: "索引失败",
};

type Props = {
  job: IndexJobStatus | null;
  published: boolean;
};

export function IndexJobStatusCard({ job, published }: Props) {
  if (!published) {
    return (
      <section className="doc-index-card muted" aria-label="索引状态">
        <p>尚未发布，暂无索引任务。</p>
      </section>
    );
  }
  if (!job) {
    return (
      <section className="doc-index-card muted" aria-label="索引状态">
        <p>暂无索引记录。</p>
      </section>
    );
  }
  return (
    <section className="doc-index-card" aria-label="索引状态">
      <h3 className="doc-section-title">索引状态</h3>
      <p>{LABELS[job.status]}</p>
      {job.status === "failed" && job.error ? (
        <p className="doc-error" role="alert">
          {job.error}
        </p>
      ) : null}
    </section>
  );
}
