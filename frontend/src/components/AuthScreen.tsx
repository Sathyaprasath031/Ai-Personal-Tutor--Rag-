import React, { useState } from "react";
import { LogIn, UserPlus, AlertCircle, GraduationCap, ShieldCheck, Sparkles, BookOpen, User } from "lucide-react";
import { api } from "../api/client";

interface AuthScreenProps {
  onAuthSuccess: (email: string) => void;
}

export const AuthScreen: React.FC<AuthScreenProps> = ({ onAuthSuccess }) => {
  const [isRegister, setIsRegister] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (isRegister && !fullName.trim()) {
      setError("Please enter your full name");
      return;
    }

    setLoading(true);

    try {
      if (isRegister) {
        const res = await api.register(email, password, fullName.trim());
        localStorage.setItem("token", res.access_token);
        localStorage.setItem("user_email", res.email);
        localStorage.setItem("user_name", fullName.trim());
        onAuthSuccess(res.email);
      } else {
        const res = await api.login(email, password);
        localStorage.setItem("token", res.access_token);
        localStorage.setItem("user_email", res.email);
        onAuthSuccess(res.email);
      }
    } catch (err: any) {
      setError(err.message || "Authentication failed. Please verify your credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh",
      width: "100vw",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: "var(--bg-app)",
      padding: "20px",
      backgroundImage: "radial-gradient(var(--border-subtle) 1px, transparent 1px)",
      backgroundSize: "24px 24px"
    }}>
      <div style={{
        width: "100%",
        maxWidth: "460px",
        backgroundColor: "var(--bg-surface)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-lg)",
        border: "1px solid var(--border-subtle)",
        overflow: "hidden"
      }}>
        {/* Brand Banner */}
        <div style={{
          backgroundColor: "var(--color-brand)",
          color: "#ffffff",
          padding: "32px 28px 24px",
          textAlign: "center",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "10px"
        }}>
          <div style={{
            width: "56px",
            height: "56px",
            borderRadius: "50%",
            backgroundColor: "rgba(255, 255, 255, 0.15)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backdropFilter: "blur(4px)"
          }}>
            <GraduationCap size={32} color="#ffffff" />
          </div>
          <div>
            <h1 style={{
              fontFamily: "var(--font-serif)",
              fontSize: "1.6rem",
              fontWeight: 600,
              margin: 0,
              letterSpacing: "-0.01em"
            }}>
              AI Personal Tutor
            </h1>
            <p style={{
              fontSize: "0.88rem",
              opacity: 0.9,
              marginTop: "4px",
              fontWeight: 400
            }}>
              Retrieval-Augmented Study Assistant
            </p>
          </div>
        </div>

        {/* Feature Badges */}
        <div style={{
          display: "flex",
          justifyContent: "center",
          gap: "12px",
          padding: "12px 20px",
          backgroundColor: "var(--bg-hover)",
          borderBottom: "1px solid var(--border-subtle)",
          fontSize: "0.76rem",
          color: "var(--text-secondary)"
        }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
            <ShieldCheck size={13} color="var(--color-brand)" /> Zero Hallucination
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
            <BookOpen size={13} color="var(--color-brand)" /> Exact Note Citations
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
            <Sparkles size={13} color="var(--color-brand)" /> Multi-Mode Tutor
          </span>
        </div>

        {/* Auth Form Container */}
        <div style={{ padding: "28px" }}>
          {/* Tabs */}
          <div style={{
            display: "flex",
            backgroundColor: "var(--bg-hover)",
            borderRadius: "var(--radius-sm)",
            padding: "4px",
            marginBottom: "20px"
          }}>
            <button
              type="button"
              onClick={() => { setIsRegister(false); setError(null); }}
              style={{
                flex: 1,
                padding: "8px 0",
                fontSize: "0.88rem",
                fontWeight: !isRegister ? 600 : 500,
                color: !isRegister ? "var(--color-brand)" : "var(--text-secondary)",
                backgroundColor: !isRegister ? "var(--bg-surface)" : "transparent",
                borderRadius: "4px",
                boxShadow: !isRegister ? "var(--shadow-sm)" : "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
                transition: "all 0.15s ease"
              }}
            >
              <LogIn size={15} />
              <span>Sign In</span>
            </button>
            <button
              type="button"
              onClick={() => { setIsRegister(true); setError(null); }}
              style={{
                flex: 1,
                padding: "8px 0",
                fontSize: "0.88rem",
                fontWeight: isRegister ? 600 : 500,
                color: isRegister ? "var(--color-brand)" : "var(--text-secondary)",
                backgroundColor: isRegister ? "var(--bg-surface)" : "transparent",
                borderRadius: "4px",
                boxShadow: isRegister ? "var(--shadow-sm)" : "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
                transition: "all 0.15s ease"
              }}
            >
              <UserPlus size={15} />
              <span>Register</span>
            </button>
          </div>

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {error && (
              <div style={{
                backgroundColor: "var(--color-danger-bg)",
                color: "var(--color-danger)",
                padding: "10px 14px",
                borderRadius: "var(--radius-sm)",
                fontSize: "0.85rem",
                display: "flex",
                alignItems: "center",
                gap: "8px",
                border: "1px solid rgba(197, 59, 39, 0.2)"
              }}>
                <AlertCircle size={16} style={{ flexShrink: 0 }} />
                <span>{error}</span>
              </div>
            )}

            {/* Full Name field — Only shown during registration */}
            {isRegister && (
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <label style={{ fontSize: "0.85rem", fontWeight: 500, color: "var(--text-secondary)" }}>
                  Full Name
                </label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  style={{
                    padding: "10px 12px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-strong)",
                    backgroundColor: "var(--bg-surface)",
                    fontSize: "0.92rem",
                    outline: "none"
                  }}
                />
              </div>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <label style={{ fontSize: "0.85rem", fontWeight: 500, color: "var(--text-secondary)" }}>
                Email Address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={{
                  padding: "10px 12px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-strong)",
                  backgroundColor: "var(--bg-surface)",
                  fontSize: "0.92rem",
                  outline: "none"
                }}
              />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <label style={{ fontSize: "0.85rem", fontWeight: 500, color: "var(--text-secondary)" }}>
                Password
              </label>
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{
                  padding: "10px 12px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-strong)",
                  backgroundColor: "var(--bg-surface)",
                  fontSize: "0.92rem",
                  outline: "none"
                }}
              />
              {isRegister && (
                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                  Must be at least 6 characters
                </span>
              )}
            </div>

            <button
              type="submit"
              className="btn-primary"
              disabled={loading}
              style={{
                width: "100%",
                padding: "11px",
                marginTop: "4px",
                fontSize: "0.92rem",
                borderRadius: "var(--radius-sm)"
              }}
            >
              {loading ? "Authenticating..." : isRegister ? "Create Account & Enter" : "Sign In & Enter"}
            </button>
          </form>

          {/* Footer note */}
          <div style={{
            marginTop: "20px",
            paddingTop: "16px",
            borderTop: "1px solid var(--border-subtle)",
            textAlign: "center",
            fontSize: "0.8rem",
            color: "var(--text-muted)",
            lineHeight: 1.5
          }}>
            <span>New student? Click <strong>Register</strong> and enter your full name to start!</span>
          </div>
        </div>
      </div>
    </div>
  );
};
