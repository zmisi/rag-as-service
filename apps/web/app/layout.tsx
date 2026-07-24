import type { Metadata } from "next";
import "./globals.css";

/** Canonical brand mark: apps/web/public/brand-cube.png (also app/icon.png). */
export const metadata: Metadata = {
  title: "lxzxai",
  description: "lxzxai — RAG as a Service",
  icons: {
    icon: [{ url: "/brand-cube.png", type: "image/png" }],
    shortcut: ["/brand-cube.png"],
    apple: [{ url: "/brand-cube.png", type: "image/png" }],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <head>
        <meta name="color-scheme" content="light dark" />
        <link rel="icon" href="/brand-cube.png" type="image/png" />
        <link rel="apple-touch-icon" href="/brand-cube.png" />
      </head>
      <body>{children}</body>
    </html>
  );
}
