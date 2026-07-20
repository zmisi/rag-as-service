"use client";

import { useState, type FormEvent } from "react";

type Props = {
  disabled: boolean;
  disabledReason?: string;
  onSend: (content: string) => Promise<void>;
};

export function Composer({ disabled, disabledReason, onSend }: Props) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const content = text.trim();
    if (!content || disabled || sending) return;
    setSending(true);
    try {
      await onSend(content);
      setText("");
    } finally {
      setSending(false);
    }
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      {disabledReason && <p className="composer-hint">{disabledReason}</p>}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="输入消息…"
        rows={3}
        disabled={disabled || sending}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            void handleSubmit(e);
          }
        }}
      />
      <button
        type="submit"
        className="btn primary"
        disabled={disabled || sending || !text.trim()}
      >
        发送
      </button>
    </form>
  );
}
