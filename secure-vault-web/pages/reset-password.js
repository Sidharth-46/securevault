import { useState } from "react";
import { useRouter } from "next/router";

// Point this at your deployed backend URL
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "https://securevault-ubnm.onrender.com";

export default function ResetPasswordPage() {
  const router = useRouter();
  const { token } = router.query;

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setMessage("");

    if (!token) {
      setError("Invalid reset link — no token provided.");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });
      const data = await res.json();
      if (data.success) {
        setMessage(data.message);
        setDone(true);
        // Redirect to desktop app after 3 seconds
        setTimeout(() => {
          window.location.href = "securevault://login";
        }, 3000);
      } else {
        setError(data.message || "Reset failed.");
      }
    } catch {
      setError("Network error — could not reach the server.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.wrapper}>
      <div style={styles.card}>
        <h1 style={styles.title}>🛡️ Secure File Vault</h1>
        <h2 style={styles.subtitle}>Reset Your Password</h2>

        {done ? (
          <div style={styles.successBox}>
            <p style={styles.successText}>{message}</p>
            <p style={styles.hint}>
              Redirecting to the desktop app…
              <br />
              <a href="securevault://login" style={styles.link}>
                Click here if not redirected
              </a>
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={styles.form}>
            <label style={styles.label}>New Password</label>
            <input
              type="password"
              placeholder="Enter new password…"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={styles.input}
              required
            />

            <label style={styles.label}>Confirm Password</label>
            <input
              type="password"
              placeholder="Re-enter password…"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              style={styles.input}
              required
            />

            {error && <p style={styles.error}>{error}</p>}

            <button
              type="submit"
              disabled={loading}
              style={{
                ...styles.button,
                opacity: loading ? 0.6 : 1,
              }}
            >
              {loading ? "Resetting…" : "Reset Password"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

const styles = {
  wrapper: {
    minHeight: "100vh",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    background: "#0f172a",
    fontFamily: "'Segoe UI', sans-serif",
    padding: 16,
  },
  card: {
    background: "#1e293b",
    borderRadius: 18,
    border: "1px solid #334155",
    padding: "40px 36px",
    maxWidth: 440,
    width: "100%",
    textAlign: "center",
  },
  title: {
    color: "#6366f1",
    fontSize: 24,
    margin: "0 0 4px",
  },
  subtitle: {
    color: "#e2e8f0",
    fontSize: 18,
    fontWeight: 500,
    margin: "0 0 24px",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
    textAlign: "left",
  },
  label: {
    color: "#94a3b8",
    fontSize: 13,
  },
  input: {
    background: "#0f172a",
    color: "#e2e8f0",
    border: "1px solid #334155",
    borderRadius: 10,
    padding: "12px 14px",
    fontSize: 14,
    outline: "none",
    width: "100%",
    boxSizing: "border-box",
  },
  button: {
    background: "#6366f1",
    color: "white",
    border: "none",
    borderRadius: 10,
    padding: "14px 0",
    fontSize: 14,
    fontWeight: "bold",
    cursor: "pointer",
    marginTop: 8,
  },
  error: {
    color: "#ef4444",
    fontSize: 13,
    margin: "4px 0 0",
    textAlign: "center",
  },
  successBox: {
    marginTop: 16,
  },
  successText: {
    color: "#22c55e",
    fontSize: 16,
    fontWeight: 600,
  },
  hint: {
    color: "#94a3b8",
    fontSize: 13,
    marginTop: 12,
  },
  link: {
    color: "#6366f1",
    textDecoration: "underline",
  },
};
