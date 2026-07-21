"use client";

import type { DocStatus } from "@/lib/documents";
import { STATUS_LABELS } from "@/lib/documents";

const STEPS: DocStatus[] = ["draft", "review", "published"];

type Props = {
  status: DocStatus;
};

export function DocStatusStepper({ status }: Props) {
  const currentIdx = STEPS.indexOf(status);

  return (
    <ol className="doc-stepper" aria-label="文档发布进度">
      {STEPS.map((step, idx) => {
        const done = idx < currentIdx;
        const active = idx === currentIdx;
        return (
          <li
            key={step}
            className={`doc-step${done ? " done" : ""}${active ? " active" : ""}`}
          >
            <span className="doc-step-dot" />
            <span>{STATUS_LABELS[step]}</span>
          </li>
        );
      })}
    </ol>
  );
}
