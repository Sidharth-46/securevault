export default function Home() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        background: "#0f172a",
        fontFamily: "'Segoe UI', sans-serif",
        color: "#e2e8f0",
      }}
    >
      <div style={{ textAlign: "center" }}>
        <h1 style={{ color: "#6366f1" }}>🛡️ Secure File Vault</h1>
        <p style={{ color: "#94a3b8" }}>
          This page is used for password recovery.
          <br />
          Open the desktop app to get started.
        </p>
      </div>
    </div>
  );
}
