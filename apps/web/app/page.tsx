export default function HomePage() {
  return (
    <main className="home">
      <h1>lxzxai</h1>
      <p>
        主站注册/登录见 F01/F02。租户聊天入口在子域，本地请用：
      </p>
      <p>
        <code>http://tenant-a.lxzxai.com:3000/chat</code>
      </p>
      <p>
        需在 <code>/etc/hosts</code> 将{" "}
        <code>tenant-a.lxzxai.com</code> 指向 <code>127.0.0.1</code>，并配置
        开发态鉴权（见 README）。
      </p>
    </main>
  );
}
