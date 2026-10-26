import React, { useState, useRef, useEffect } from "react";
import { ChevronUp, Check, Sparkles, BookOpen, Baby, ListOrdered, HelpCircle, HelpCircle as QuestionMark } from "lucide-react";
import { TutorMode } from "../types";

interface ModeSelectorProps {
  currentMode: TutorMode;
  onChange: (mode: TutorMode) => void;
  disabled?: boolean;
}

const MODES: { id: TutorMode; label: string; desc: string }[] = [
  { id: "explain", label: "Explain", desc: "Intuition, formal definitions, examples & check questions" },
  { id: "summary", label: "Exam Sheet", desc: "Chunk complex notes into core takeaways, traps & memory tricks" },
  { id: "eli5", label: "ELI5", desc: "Explain Like I'm 5 with vivid everyday analogies & zero jargon" },
  { id: "steps", label: "Step-by-step", desc: "Numbered derivations, algorithmic steps and worked solutions" },
  { id: "quiz", label: "Quiz me", desc: "Generate 3 targeted practice questions from your notes" },
  { id: "socratic", label: "Socratic", desc: "Guided critical thinking with one leading question at a time" },
];

export const ModeSelector: React.FC<ModeSelectorProps> = ({ currentMode, onChange, disabled }) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close popup menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const activeModeObj = MODES.find((m) => m.id === currentMode) || MODES[0];

  return (
    <div ref={containerRef} style={{ position: "relative", display: "inline-block" }}>
      {/* Upward Popup Menu */}
      {isOpen && (
        <div
          style={{
            position: "absolute",
            bottom: "calc(100% + 10px)",
            left: 0,
            width: "300px",
            backgroundColor: "var(--bg-surface)",
            border: "1px solid var(--border-strong)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-lg)",
            padding: "6px",
            display: "flex",
            flexDirection: "column",
            gap: "2px",
            zIndex: 100,
            animation: "fadeIn 0.15s cubic-bezier(0.16, 1, 0.3, 1)",
          }}
        >
          <div style={{
            padding: "8px 10px 6px",
            fontSize: "0.74rem",
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            color: "var(--text-muted)",
            borderBottom: "1px solid var(--border-subtle)",
            marginBottom: "4px"
          }}>
            Tutor Mode
          </div>

          {MODES.map((m) => {
            const isActive = currentMode === m.id;
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => {
                  onChange(m.id);
                  setIsOpen(false);
                }}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  justifyContent: "space-between",
                  padding: "8px 10px",
                  borderRadius: "var(--radius-sm)",
                  backgroundColor: isActive ? "rgba(255, 255, 255, 0.08)" : "transparent",
                  color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                  textAlign: "left",
                  transition: "all var(--transition-fast)",
                  cursor: "pointer",
                }}
                onMouseEnter={(e) => {
                  if (!isActive) e.currentTarget.style.backgroundColor = "var(--bg-surface-hover)";
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.backgroundColor = "transparent";
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                  <span style={{ fontSize: "0.86rem", fontWeight: isActive ? 600 : 500, color: "var(--text-primary)" }}>
                    {m.label}
                  </span>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", lineHeight: 1.35 }}>
                    {m.desc}
                  </span>
                </div>
                {isActive && (
                  <Check size={14} color="var(--color-brand)" style={{ marginTop: "3px", flexShrink: 0 }} />
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Modern ChatGPT Angular Up Button */}
      <button
        type="button"
        onClick={() => !disabled && setIsOpen((prev) => !prev)}
        disabled={disabled}
        title="Change tutor teaching mode"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "6px",
          backgroundColor: isOpen ? "var(--bg-surface-hover)" : "rgba(255, 255, 255, 0.06)",
          border: "1px solid var(--border-subtle)",
          padding: "5px 10px",
          borderRadius: "var(--radius-full)",
          color: "var(--text-secondary)",
          fontSize: "0.8rem",
          fontWeight: 500,
          cursor: disabled ? "not-allowed" : "pointer",
          transition: "all var(--transition-fast)",
        }}
        onMouseEnter={(e) => {
          if (!disabled) {
            e.currentTarget.style.backgroundColor = "var(--bg-surface-hover)";
            e.currentTarget.style.color = "var(--text-primary)";
          }
        }}
        onMouseLeave={(e) => {
          if (!disabled && !isOpen) {
            e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.06)";
            e.currentTarget.style.color = "var(--text-secondary)";
          }
        }}
      >
        <span>{activeModeObj.label}</span>
        <ChevronUp
          size={14}
          style={{
            transform: isOpen ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform var(--transition-fast)",
          }}
        />
      </button>
    </div>
  );
};
