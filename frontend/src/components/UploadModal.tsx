import React, { useState, useRef, useEffect, useCallback } from "react";
import { X, UploadCloud, FileText, Trash2, AlertCircle, CheckCircle2, Clock, Loader2, Plus } from "lucide-react";
import { api } from "../api/client";
import { DocumentItem, Subject } from "../types";

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  subjectId: string | null;
  subjectName: string;
  subjects?: Subject[];
  onSelectSubject?: (id: string) => void;
  onCreateSubject?: (name: string) => Promise<void>;
  onDocumentsUpdated?: () => void;
  onToast?: (message: string, type?: "success" | "error" | "info") => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  subjectId,
  subjectName,
  subjects = [],
  onSelectSubject,
  onCreateSubject,
  onDocumentsUpdated,
  onToast,
}) => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [newSubjectInput, setNewSubjectInput] = useState("");
  const [isCreatingSubject, setIsCreatingSubject] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch documents for this subject
  const loadDocuments = useCallback(async () => {
    if (!subjectId) {
      setDocuments([]);
      return;
    }
    try {
      const docs = await api.getDocuments(subjectId);
      setDocuments(docs);
      if (onDocumentsUpdated) {
        onDocumentsUpdated();
      }
    } catch (err: any) {
      console.error("Failed to load documents:", err);
    }
  }, [subjectId, onDocumentsUpdated]);

  useEffect(() => {
    if (isOpen) {
      loadDocuments();
    }
  }, [isOpen, loadDocuments]);

  // Polling for processing / queued documents
  useEffect(() => {
    if (!isOpen || !subjectId) return;

    const hasPending = documents.some((d) => d.status === "queued" || d.status === "processing");
    if (!hasPending) return;

    const interval = setInterval(() => {
      loadDocuments();
    }, 2500);

    return () => clearInterval(interval);
  }, [isOpen, subjectId, documents, loadDocuments]);

  // Handle file upload
  const handleUploadFiles = async (files: FileList | File[]) => {
    if (!files || files.length === 0) return;
    if (!subjectId) {
      setErrorMessage("Please select or create a subject before uploading files.");
      return;
    }

    setIsUploading(true);
    setErrorMessage(null);

    const allowed = [".pdf", ".docx", ".pptx", ".txt", ".md"];

    try {
      for (const file of Array.from(files)) {
        const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
        if (!allowed.includes(ext)) {
          throw new Error(`File ${file.name} has unsupported type. Allowed: PDF, DOCX, PPTX, TXT, MD.`);
        }
        await api.uploadDocument(subjectId, file);
      }
      await loadDocuments();
    } catch (err: any) {
      setErrorMessage(err.message || "Upload failed");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleCreateNewSubject = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newSubjectInput.trim();
    if (!trimmed || !onCreateSubject) return;

    setIsCreatingSubject(true);
    setErrorMessage(null);
    try {
      await onCreateSubject(trimmed);
      setNewSubjectInput("");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to create subject");
    } finally {
      setIsCreatingSubject(false);
    }
  };

  const handleDelete = async (docId: string, filename: string) => {
    try {
      await api.deleteDocument(docId);
      await loadDocuments();
      if (onToast) {
        onToast(`"${filename}" deleted`, "info");
      }
    } catch (err: any) {
      if (onToast) {
        onToast(err.message || "Failed to delete document", "error");
      } else {
        setErrorMessage(err.message || "Failed to delete document");
      }
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleUploadFiles(e.dataTransfer.files);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <UploadCloud size={18} color="var(--color-brand)" />
            <h2 style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-primary)" }}>
              {subjectName ? `Manage Notes — ${subjectName}` : "Upload Course Materials"}
            </h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" style={{ color: "var(--text-muted)", padding: "4px" }}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          {/* Error Banner */}
          {errorMessage && (
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
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Subject Selector or Creator if none selected */}
          {!subjectId && (
            <div style={{
              backgroundColor: "var(--bg-app)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-sm)",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              gap: "12px"
            }}>
              <span style={{ fontSize: "0.88rem", fontWeight: 500, color: "var(--text-primary)" }}>
                Select or create a subject to upload your notes:
              </span>

              {subjects.length > 0 && onSelectSubject && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                  {subjects.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      className="btn-secondary"
                      onClick={() => onSelectSubject(s.id)}
                      style={{ fontSize: "0.82rem", padding: "6px 12px" }}
                    >
                      {s.name}
                    </button>
                  ))}
                </div>
              )}

              {onCreateSubject && (
                <form onSubmit={handleCreateNewSubject} style={{ display: "flex", gap: "6px", marginTop: "4px" }}>
                  <input
                    type="text"
                    className="new-subject-input"
                    placeholder="Subject name (e.g. AI Governance, Cloud...)"
                    value={newSubjectInput}
                    onChange={(e) => setNewSubjectInput(e.target.value)}
                    disabled={isCreatingSubject}
                  />
                  <button
                    type="submit"
                    className="btn-primary"
                    disabled={!newSubjectInput.trim() || isCreatingSubject}
                  >
                    <Plus size={14} />
                    <span>Create & Select</span>
                  </button>
                </form>
              )}
            </div>
          )}

          {/* Dropzone */}
          {subjectId && (
            <div
              className={`dropzone ${dragActive ? "active" : ""}`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.pptx,.txt,.md"
                onChange={(e) => e.target.files && handleUploadFiles(e.target.files)}
                style={{ display: "none" }}
              />

              {isUploading ? (
                <>
                  <Loader2 size={32} color="var(--color-brand)" className="animate-spin" />
                  <span style={{ fontSize: "0.9rem", color: "var(--text-secondary)" }}>
                    Uploading & extracting text...
                  </span>
                </>
              ) : (
                <>
                  <UploadCloud size={32} color="var(--text-muted)" />
                  <div>
                    <span style={{ fontWeight: 600, color: "var(--color-brand)" }}>Click to browse</span>
                    <span style={{ color: "var(--text-muted)" }}> or drag and drop your lecture notes</span>
                  </div>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    Supported: PDF, DOCX, PPTX, TXT, Markdown (Max 50MB)
                  </span>
                </>
              )}
            </div>
          )}

          {/* Document list */}
          {subjectId && (
            <div>
              <div style={{
                fontSize: "0.75rem",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                color: "var(--text-muted)",
                marginBottom: "8px"
              }}>
                Uploaded Notes ({documents.length})
              </div>

              {documents.length === 0 ? (
                <div style={{
                  padding: "20px",
                  textAlign: "center",
                  fontSize: "0.85rem",
                  color: "var(--text-muted)",
                  border: "1px dashed var(--border-subtle)",
                  borderRadius: "var(--radius-sm)"
                }}>
                  No documents in this subject yet. Upload your first PDF, DOCX, or PPTX above!
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "240px", overflowY: "auto" }}>
                  {documents.map((doc) => {
                    const isReady = doc.status === "ready";
                    const isProcessing = doc.status === "processing" || doc.status === "queued";
                    const isFailed = doc.status === "failed";

                    return (
                      <div
                        key={doc.id}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "10px 12px",
                          borderRadius: "var(--radius-sm)",
                          backgroundColor: "var(--bg-app)",
                          border: "1px solid var(--border-subtle)"
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "10px", overflow: "hidden" }}>
                          <FileText size={18} color="var(--color-brand)" style={{ flexShrink: 0 }} />
                          <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
                            <span style={{
                              fontSize: "0.86rem",
                              fontWeight: 500,
                              color: "var(--text-primary)",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap"
                            }}>
                              {doc.filename}
                            </span>
                            <span style={{ fontSize: "0.74rem", color: "var(--text-muted)" }}>
                              {doc.pages ? `${doc.pages} pages • ` : ""}
                              {doc.file_size ? `${Math.round(doc.file_size / 1024)} KB` : ""}
                            </span>
                          </div>
                        </div>

                        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexShrink: 0 }}>
                          {isReady && (
                            <span className="status-badge ready">
                              <CheckCircle2 size={11} /> Ready
                            </span>
                          )}
                          {isProcessing && (
                            <span className="status-badge processing">
                              <Clock size={11} className="animate-spin" /> Indexing
                            </span>
                          )}
                          {isFailed && (
                            <span className="status-badge failed">
                              <AlertCircle size={11} /> Failed
                            </span>
                          )}

                          <button
                            type="button"
                            onClick={() => handleDelete(doc.id, doc.filename)}
                            title="Delete file"
                            aria-label={`Delete ${doc.filename}`}
                            style={{ color: "var(--text-muted)", padding: "4px" }}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
