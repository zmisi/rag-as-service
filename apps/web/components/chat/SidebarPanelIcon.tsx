/** Shared panel/sidebar toggle glyph (filled left rail in a rounded square). */
export function SidebarPanelIcon({ size = 18 }: { size?: number }) {
  return (
    <svg
      viewBox="0 0 16 16"
      width={size}
      height={size}
      aria-hidden="true"
      focusable="false"
    >
      <rect
        x="1.75"
        y="2.25"
        width="12.5"
        height="11.5"
        rx="2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.35"
      />
      <rect
        x="2.9"
        y="3.4"
        width="3.1"
        height="9.2"
        rx="0.6"
        fill="currentColor"
      />
    </svg>
  );
}
