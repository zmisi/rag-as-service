/** Speech-bubble with plus — new conversation / New task glyph. */
export function NewTaskIcon({ size = 16 }: { size?: number }) {
  return (
    <svg
      viewBox="0 0 16 16"
      width={size}
      height={size}
      aria-hidden="true"
      focusable="false"
    >
      {/* Circle bubble with small tail at ~7 o'clock */}
      <path
        d="M8 1.9a5.7 5.7 0 0 1 2.05 11.02c-.55.2-1.5.72-2.55 1.18a.48.48 0 0 1-.68-.5l.32-1.72A5.7 5.7 0 0 1 8 1.9Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.35"
        strokeLinejoin="round"
      />
      <path
        d="M8 5.15v5.7M5.15 8h5.7"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.35"
        strokeLinecap="round"
      />
    </svg>
  );
}
