import React, { useState } from "react";
import { X, LogIn, UserPlus, AlertCircle, CheckCircle } from "lucide-react";
import { api } from "../api/client";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthSuccess: (email: string) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onAuthSuccess }) => {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isRegister) {
        const res = await api.register(email, password);
        localStorage.setItem("token", res.access_token);
        localStorage.setItem("user_email", res.email);
        onAuthSuccess(res.email);
      } else {
        const res = await api.login(email, password);
        localStorage.setItem("token", res.access_token);
        localStorage.setItem("user_email", res.email);
        onAuthSuccess(res.email);
      }
      onClose();
    } catch (err: any) {
      setError(err.message || "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" style={{ maxWidth: "420px" }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 600 }}>
            {isRegister ? <UserPlus size={18} color="var(--color-brand)" /> : <LogIn size={18} color="var(--color-brand)" />}
            <span>{isRegister ? "Create an Account" : "Sign In to Personal Tutor"}</span>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" style={{ color: "var(--text-muted)", fontSize: "1.2rem" }}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: "16px" }}>
          {error && (
            <div style={{
              backgroundColor: "var(--color-danger-bg)",
              color: "var(--color-danger)",
              padding: "10px 14px",
              borderRadius: "var(--radius-sm)",
              fontSize: "0.85rem",
              display: "flex",
              alignItems: "center",
              gap: "8px"
            }}>
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <label style={{ fontSize: "0.85rem", fontWeight: 500, color: "var(--text-secondary)" }}>Email Address</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{
                padding: "8px 12px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-strong)",
                backgroundColor: "var(--bg-surface)",
                fontSize: "0.9rem",
              }}
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <label style={{ fontSize: "0.85rem", fontWeight: 500, color: "var(--text-secondary)" }}>Password</label>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{
                padding: "8px 12px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-strong)",
                backgroundColor: "var(--bg-surface)",
                fontSize: "0.9rem",
              }}
            />
            {isRegister && (
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Must be at least 6 characters</span>
            )}
          </div>

          <button
            type="submit"
            className="btn-primary"
            disabled={loading}
            style={{ width: "100%", padding: "10px", marginTop: "6px" }}
          >
            {loading ? "Processing..." : isRegister ? "Sign Up" : "Sign In"}
          </button>

          <div style={{ textAlign: "center", fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "4px" }}>
            {isRegister ? (
              <span>
                Already have an account?{" "}
                <button
                  type="button"
                  onClick={() => { setIsRegister(false); setError(null); }}
                  style={{ color: "var(--color-brand)", fontWeight: 600, textDecoration: "underline" }}
                >
                  Sign In
                </button>
              </span>
            ) : (
              <span>
                Don't have an account?{" "}
                <button
                  type="button"
                  onClick={() => { setIsRegister(true); setError(null); }}
                  style={{ color: "var(--color-brand)", fontWeight: 600, textDecoration: "underline" }}
                >
                  Create one
                </button>
              </span>
            )}
          </div>
        </form>
      </div>
    </div>
  );
};
