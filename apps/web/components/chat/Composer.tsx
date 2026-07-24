"use client";

import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";

type Props = {
  disabled: boolean;
  disabledReason?: string;
  placeholder?: string;
  onSend: (content: string) => Promise<void>;
};

export function Composer({
  disabled,
  disabledReason,
  placeholder = "询问或输入消息…",
  onSend,
}: Props) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const composingRef = useRef(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  function resizeTextarea() {
    const el = textareaRef.current;
    if (!el) return;
    const styles = window.getComputedStyle(el);
    const minH = parseFloat(styles.minHeight) || 0;
    const maxH = parseFloat(styles.maxHeight) || Number.POSITIVE_INFINITY;
    el.style.height = "0px";
    const next = Math.min(Math.max(el.scrollHeight, minH), maxH);
    el.style.height = `${next}px`;
  }

  useLayoutEffect(() => {
    resizeTextarea();
  }, [text]);

  useEffect(() => {
    const onResize = () => resizeTextarea();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

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
    <div className="composer-wrap" data-testid="portal-composer">
      <form className="composer" onSubmit={handleSubmit}>
        {disabledReason && <p className="composer-hint">{disabledReason}</p>}
        <div className="composer-row">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={placeholder}
            rows={1}
            disabled={disabled || sending}
            onCompositionStart={() => {
              composingRef.current = true;
            }}
            onCompositionEnd={() => {
              composingRef.current = false;
            }}
            onKeyDown={handleKeyDown}
            onInput={resizeTextarea}
          />
          <button
            type="submit"
            className="btn send"
            disabled={disabled || sending || !text.trim()}
            aria-label="发送"
            title="发送"
          >
            <svg
              className="send-arrow"
              viewBox="0 0 16 16"
              width="16"
              height="16"
              aria-hidden="true"
              focusable="false"
            >
              <path
                d="M8 12.5V3.5M8 3.5L4.5 7M8 3.5L11.5 7"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
      </form>
    </div>
  );
}
