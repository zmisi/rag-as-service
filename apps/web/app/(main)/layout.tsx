export default function MainLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <main style={{ maxWidth: 480, margin: "2rem auto", padding: "0 1rem" }}>
      <header style={{ marginBottom: "1.5rem" }}>
        <p style={{ margin: 0, color: "#666" }}>lxzxai.com</p>
        <nav style={{ display: "flex", gap: "1rem", marginTop: "0.5rem" }}>
          <a href="/login">登录</a>
          <a href="/register">注册</a>
        </nav>
      </header>
      {children}
    </main>
  );
}
