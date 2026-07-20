import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "rag-as-service",
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
