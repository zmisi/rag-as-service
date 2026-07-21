import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "lxzxai",
  description: "RAG as a Service",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
