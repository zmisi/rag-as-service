"use client";

import type { IngestJobStatus } from "@/lib/documents";

const LABELS: Record<IngestJobStatus["status"], string> = {
  pending: "摄入排队中…",
  running: "摄入进行中…",
  succeeded: "摄入成功",
  failed: "摄入失败",
};

type Props = {
  job: IngestJobStatus | null;
  published: boolean;
};

export function IngestJobStatusCard({ job, published }: Props) {
  if (!published) {
    return (
      <section className="doc-index-card muted" aria-label="摄入状态">
        <p>尚未发布，暂无摄入任务。</p>
      </section>
    );
  }
  if (!job) {
    return (
      <section className="doc-index-card muted" aria-label="摄入状态">
        <p>暂无摄入记录。</p>
      </section>
    );
  }
  return (
    <section className="doc-index-card" aria-label="摄入状态">
      <h3 className="doc-section-title">摄入状态</h3>
      <p>{LABELS[job.status]}</p>
      {job.warning ? (
        <p className="doc-alert-warning" role="status">
          {job.warning}
        </p>
      ) : null}
      {job.status === "failed" && job.error ? (
        <p className="doc-error" role="alert">
          {job.error}
        </p>
      ) : null}
    </section>
  );
}
