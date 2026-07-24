"use client";

import type { FaqSuggestion } from "@/lib/api";

type Props = {
  items: FaqSuggestion[];
  busy: boolean;
  onSelect: (item: FaqSuggestion) => void;
  onRefresh: () => void;
};

export function FaqSuggestions({ items, busy, onSelect, onRefresh }: Props) {
  if (items.length === 0) return null;

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
      <ul className="faq-chip-list">
        {items.map((item) => (
          <li key={item.document_group_id}>
            <button
              type="button"
              className="faq-chip"
              disabled={busy}
              onClick={() => onSelect(item)}
            >
              {item.hot && <span className="faq-hot">hot</span>}
              <span className="faq-chip-text">{item.question}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
