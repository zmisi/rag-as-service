"use client";

import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";

type Props = {
  disabled: boolean;
  disabledReason?: string;
  onSend: (content: string) => Promise<void>;
};

export function Composer({ disabled, disabledReason, onSend }: Props) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const composingRef = useRef(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (composingRef.current) return;
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

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key !== "Enter" || e.shiftKey) return;
    // IME: Enter confirms candidate — do not send (match Cursor / macOS Chinese input).
    if (composingRef.current || e.nativeEvent.isComposing || e.keyCode === 229) {
      return;
    }
    e.preventDefault();
    void handleSubmit(e);
  }

  return (
    <div className="composer-wrap">
      <form className="composer" onSubmit={handleSubmit}>
        {disabledReason && <p className="composer-hint">{disabledReason}</p>}
        <div className="composer-row">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="询问或输入消息…"
            rows={2}
            disabled={disabled || sending}
            onCompositionStart={() => {
              composingRef.current = true;
            }}
            onCompositionEnd={() => {
              composingRef.current = false;
            }}
            onKeyDown={handleKeyDown}
          />
          <button
            type="submit"
            className="btn send"
            disabled={disabled || sending || !text.trim()}
            aria-label="发送"
            title="发送"
          >
            ↑
          </button>
        </div>
      </form>
    </div>
  );
}
