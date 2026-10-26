import React, { useState } from "react";
import { Plus, BookMarked, Trash2, X, GraduationCap, User, LogOut, LogIn } from "lucide-react";
import { Subject } from "../types";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  subjects: Subject[];
  activeSubjectId: string | null;
  onSelectSubject: (id: string) => void;
  onCreateSubject: (name: string) => Promise<void>;
  onDeleteSubject: (id: string) => Promise<void>;
  onOpenUpload: () => void;
  userEmail: string | null;
  onOpenAuth: () => void;
  onLogout: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onClose,
  subjects,
  activeSubjectId,
  onSelectSubject,
  onCreateSubject,
  onDeleteSubject,
  onOpenUpload,
  userEmail,
  onOpenAuth,
  onLogout,
}) => {
  const [newSubjectName, setNewSubjectName] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newSubjectName.trim();
    if (!trimmed) return;
    setIsCreating(true);
    try {
      await onCreateSubject(trimmed);
      setNewSubjectName("");
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <aside className={`sidebar ${isOpen ? "open" : ""}`} aria-label="Study subjects sidebar">
      <div className="sidebar-header">
        <div className="sidebar-title">
          <GraduationCap size={22} />
          <span>Personal Tutor</span>
        </div>
        <button
          type="button"
          className="sidebar-close-btn"
          onClick={onClose}
          aria-label="Close sidebar"
        >
          <X size={18} />
        </button>
      </div>

      <div className="sidebar-content">
        {/* User Profile / Auth Section */}
        <div style={{
          backgroundColor: "var(--bg-surface)",
          padding: "10px 12px",
          borderRadius: "var(--radius-sm)",
          border: "1px solid var(--border-subtle)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: "0.85rem"
        }}>
          {userEmail ? (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", overflow: "hidden" }}>
                <User size={16} color="var(--color-brand)" style={{ flexShrink: 0 }} />
                <span style={{
                  textOverflow: "ellipsis",
                  overflow: "hidden",
                  whiteSpace: "nowrap",
                  maxWidth: "140px",
                  fontWeight: 500
                }}>
                  {userEmail}
                </span>
              </div>
              <button
                type="button"
                onClick={onLogout}
                title="Sign Out"
                aria-label="Sign Out"
                style={{
                  color: "var(--color-danger)",
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                  fontSize: "0.78rem",
                  padding: "4px 6px",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--color-danger-bg)"
                }}
              >
                <LogOut size={13} />
                <span>Exit</span>
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={onOpenAuth}
              style={{
                width: "100%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                color: "var(--color-brand)",
                fontWeight: 600,
                padding: "4px 0"
              }}
            >
              <LogIn size={15} />
              <span>Sign In / Register</span>
            </button>
          )}
        </div>

        <div>
          <div className="section-label">Subjects & Courses</div>
          <div className="subject-list">
            {subjects.length === 0 ? (
              <div style={{ padding: "12px 8px", fontSize: "0.85rem", color: "var(--text-muted)" }}>
                No subjects yet. Create one below to begin.
              </div>
            ) : (
              subjects.map((sub) => {
                const isActive = sub.id === activeSubjectId;
                return (
                  <div
                    key={sub.id}
                    className={`subject-item ${isActive ? "active" : ""}`}
                    onClick={() => {
                      onSelectSubject(sub.id);
                      if (window.innerWidth <= 768) onClose();
                    }}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        onSelectSubject(sub.id);
                      }
                    }}
                  >
                    <div className="subject-item-title">
                      <BookMarked size={16} color={isActive ? "var(--color-brand)" : "var(--text-muted)"} />
                      <span>{sub.name}</span>
                    </div>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSubject(sub.id);
                      }}
                      title={`Delete ${sub.name}`}
                      aria-label={`Delete subject ${sub.name}`}
                      style={{ color: "var(--text-muted)", padding: "2px", opacity: 0.7 }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                );
              })
            )}
          </div>

          {/* New Subject Form */}
          <form onSubmit={handleSubmit} className="new-subject-form">
            <input
              type="text"
              className="new-subject-input"
              placeholder="e.g. AI Governance, Cloud..."
              value={newSubjectName}
              onChange={(e) => setNewSubjectName(e.target.value)}
              disabled={isCreating}
              aria-label="New subject name"
            />
            <button
              type="submit"
              className="btn-primary"
              disabled={!newSubjectName.trim() || isCreating}
              title="Add subject"
              aria-label="Add subject"
            >
              <Plus size={15} />
            </button>
          </form>
        </div>
      </div>
    </aside>
  );
};
