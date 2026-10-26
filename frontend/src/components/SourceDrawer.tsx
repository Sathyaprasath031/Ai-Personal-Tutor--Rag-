import React, { useEffect } from "react";
import { X, FileText, Bookmark, Target } from "lucide-react";
import { SourceCitation } from "../types";

interface SourceDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  selectedSourceId: string | null;
  sources: SourceCitation[];
}

export const SourceDrawer: React.FC<SourceDrawerProps> = ({
  isOpen,
  onClose,
  selectedSourceId,
  sources,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const activeSource = sources.find((s) => s.id === selectedSourceId) || sources[0];

  return (
    <>
      <div className="source-drawer-backdrop" onClick={onClose} aria-hidden="true" />
      <aside className="source-drawer" aria-label="Source citation details">
        <div className="source-drawer-header">
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <FileText size={18} color="var(--color-brand)" />
            <h2 style={{ fontSize: "1.05rem", fontWeight: 600 }}>Source Citations</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close source drawer"
            style={{ padding: "4px", borderRadius: "4px", color: "var(--text-muted)" }}
          >
            <X size={18} />
          </button>
        </div>

        <div className="source-drawer-content">
          {sources.length === 0 ? (
            <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
              No sources cited for this response.
            </p>
          ) : (
            sources.map((source) => {
              const isSelected = activeSource?.id === source.id;
              const pagesLabel =
                source.page_start === source.page_end
                  ? `Page ${source.page_start}`
                  : `Pages ${source.page_start}–${source.page_end}`;

              return (
                <div
                  key={source.id}
                  className="source-card"
                  style={{
                    borderColor: isSelected ? "var(--color-citation)" : "var(--border-subtle)",
                    backgroundColor: isSelected ? "#fffaf7" : "var(--bg-app)",
                  }}
                >
                  <div className="source-card-header">
                    <span className="source-card-file">{source.filename}</span>
                    <span className="source-card-pages">{pagesLabel}</span>
                  </div>

                  <div className="source-card-section">
                    <Bookmark size={13} style={{ display: "inline", marginRight: "4px" }} />
                    Section: {source.section}
                  </div>

                  {source.score !== undefined && (
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "6px" }}>
                      <Target size={11} style={{ display: "inline", marginRight: "4px" }} />
                      Relevance confidence: {(source.score * 100).toFixed(0)}%
                    </div>
                  )}

                  <div className="source-card-snippet">
                    "{source.snippet}"
                  </div>
                </div>
              );
            })
          )}
        </div>
      </aside>
    </>
  );
};
