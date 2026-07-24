"use client";

import type { FaqSuggestion } from "@/lib/api";

type Props = {
  items: FaqSuggestion[];
  busy: boolean;
  onSelect: (item: FaqSuggestion) => void;
  onRefresh: () => void;
};

/** Soft pastel tones for wrap pills (hot uses coral slot). */
const PILL_TONES = ["teal", "sky", "sage", "sand"] as const;

export function FaqSuggestions({ items, busy, onSelect, onRefresh }: Props) {
  if (items.length === 0) return null;

  let toneIdx = 0;

  return (
    <section className="faq-suggestions" aria-label="FAQ 推荐">
      <div className="faq-suggestions-header">
        <span className="faq-suggestions-label">猜你想问</span>
        <button
          type="button"
          className="btn ghost"
          disabled={busy}
          onClick={onRefresh}
        >
          换一批
        </button>
      </div>
      <ul className="faq-pill-list">
        {items.map((item) => {
          const tone = item.hot
            ? "hot"
            : PILL_TONES[toneIdx++ % PILL_TONES.length];
          return (
            <li key={item.document_group_id}>
              <button
                type="button"
                className={`faq-pill faq-pill-${tone}`}
                data-hot={item.hot ? "true" : "false"}
                disabled={busy}
                onClick={() => onSelect(item)}
              >
                {item.hot && (
                  <span className="faq-hot-emoji" aria-hidden="true">
                    🔥
                  </span>
                )}
                <span className="faq-pill-text">{item.question}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
