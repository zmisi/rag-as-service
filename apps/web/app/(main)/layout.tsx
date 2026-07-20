export default function MainLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <main style={{ maxWidth: 480, margin: "2rem auto", padding: "0 1rem" }}>
      <header style={{ marginBottom: "1.5rem" }}>
        <p style={{ margin: 0, color: "#666" }}>lxzxai.com</p>
      </header>
      {children}
    </main>
  );
}
