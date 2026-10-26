import React, { useEffect } from "react";
import { CheckCircle2, AlertCircle, Info, X } from "lucide-react";

export type ToastType = "success" | "error" | "info";

export interface ToastMessage {
  id: string;
  type: ToastType;
  message: string;
}

interface ToastProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export const Toast: React.FC<ToastProps> = ({ toasts, onDismiss }) => {
  return (
    <div
      style={{
        position: "fixed",
        top: "20px",
        left: "50%",
        transform: "translateX(-50%)",
        display: "flex",
        flexDirection: "column",
        gap: "8px",
        zIndex: 9999,
        pointerEvents: "none",
        width: "max-content",
        maxWidth: "90vw",
      }}
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
};

const ToastItem: React.FC<{ toast: ToastMessage; onDismiss: (id: string) => void }> = ({
  toast,
  onDismiss,
}) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onDismiss(toast.id);
    }, 3500);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  const isSuccess = toast.type === "success";
  const isError = toast.type === "error";

  return (
    <div
      style={{
        pointerEvents: "auto",
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: "10px 16px",
        borderRadius: "var(--radius-md)",
        backgroundColor: "var(--bg-surface)",
        color: "var(--text-primary)",
        border: "1px solid var(--border-strong)",
        boxShadow: "var(--shadow-lg)",
        fontSize: "0.88rem",
        fontWeight: 500,
        animation: "slideDown 0.25s cubic-bezier(0.16, 1, 0.3, 1) both",
      }}
    >
      {isSuccess && <CheckCircle2 size={16} color="var(--color-brand)" style={{ flexShrink: 0 }} />}
      {isError && <AlertCircle size={16} color="var(--color-danger)" style={{ flexShrink: 0 }} />}
      {!isSuccess && !isError && <Info size={16} color="var(--color-citation)" style={{ flexShrink: 0 }} />}

      <span>{toast.message}</span>

      <button
        type="button"
        onClick={() => onDismiss(toast.id)}
        aria-label="Dismiss toast"
        style={{
          color: "var(--text-muted)",
          padding: "2px",
          marginLeft: "6px",
          cursor: "pointer",
        }}
      >
        <X size={14} />
      </button>
    </div>
  );
};
