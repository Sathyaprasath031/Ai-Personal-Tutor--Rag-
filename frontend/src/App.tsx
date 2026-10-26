import React, { useState, useEffect, useRef, useCallback } from "react";
import { Menu, UploadCloud, AlertCircle, User, LogOut } from "lucide-react";
import { api } from "./api/client";
import { streamChat } from "./api/stream";
import { Subject, Message, SourceCitation, TutorMode } from "./types";
import { Sidebar } from "./components/Sidebar";
import { ChatWindow } from "./components/ChatWindow";
import { UploadModal } from "./components/UploadModal";
import { SourceDrawer } from "./components/SourceDrawer";
import { AuthScreen } from "./components/AuthScreen";
import { Toast, ToastMessage } from "./components/Toast";

export const App: React.FC = () => {
  // Authentication State: Require valid token and user_email to access app
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("token") || null);
  const [userEmail, setUserEmail] = useState<string | null>(() => localStorage.getItem("user_email") || null);

  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [activeSubjectId, setActiveSubjectId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentMode, setCurrentMode] = useState<TutorMode>("explain");
  const [conversationId, setConversationId] = useState<string | null>(null);

  // Modals & Drawers
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSourceDrawerOpen, setIsSourceDrawerOpen] = useState(false);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [activeSources, setActiveSources] = useState<SourceCitation[]>([]);

  // Errors & notifications
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = (message: string, type: "success" | "error" | "info" = "info") => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`;
    setToasts((prev) => [...prev, { id, message, type }]);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Abort controller reference for cancelling generation
  const abortControllerRef = useRef<AbortController | null>(null);

  // Handle successful login or registration
  const handleAuthSuccess = (email: string) => {
    const savedToken = localStorage.getItem("token");
    setToken(savedToken);
    setUserEmail(email);
    setMessages([]);
    setConversationId(null);
    setActiveSubjectId(null);
  };

  // Handle logout
  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user_email");
    setToken(null);
    setUserEmail(null);
    setSubjects([]);
    setActiveSubjectId(null);
    setMessages([]);
    setConversationId(null);
  };

  // Load subjects only when authenticated
  const loadSubjects = useCallback(async () => {
    if (!token) return;
    try {
      const list = await api.getSubjects();
      setSubjects(list);
      if (list.length > 0 && !activeSubjectId) {
        setActiveSubjectId(list[0].id);
      } else if (list.length === 0) {
        setActiveSubjectId(null);
      }
    } catch (err: any) {
      if (err.message && (err.message.includes("401") || err.message.toLowerCase().includes("credentials"))) {
        handleLogout();
        return;
      }
      setErrorBanner(err.message || "Failed to load subjects");
    }
  }, [token, activeSubjectId]);

  useEffect(() => {
    if (token) {
      loadSubjects();
    }
  }, [loadSubjects, token]);

  const activeSubject = subjects.find((s) => s.id === activeSubjectId) || null;

  // Create subject
  const handleCreateSubject = async (name: string) => {
    try {
      const created = await api.createSubject(name);
      setSubjects((prev) => [...prev, created]);
      setActiveSubjectId(created.id);
      setMessages([]);
      setConversationId(null);
    } catch (err: any) {
      setErrorBanner(err.message || "Failed to create subject");
    }
  };

  // Delete subject
  const handleDeleteSubject = async (id: string) => {
    const targetSub = subjects.find((s) => s.id === id);
    const subName = targetSub ? targetSub.name : "Subject";
    try {
      await api.deleteSubject(id);
      setSubjects((prev) => prev.filter((s) => s.id !== id));
      if (activeSubjectId === id) {
        const remaining = subjects.filter((s) => s.id !== id);
        setActiveSubjectId(remaining.length > 0 ? remaining[0].id : null);
        setMessages([]);
        setConversationId(null);
      }
      addToast(`"${subName}" deleted successfully`, "info");
    } catch (err: any) {
      addToast(err.message || "Failed to delete subject", "error");
    }
  };

  // Switch subject
  const handleSelectSubject = (id: string) => {
    if (id === activeSubjectId) return;
    setActiveSubjectId(id);
    setMessages([]);
    setConversationId(null);
  };

  // Open upload modal
  const handleOpenUpload = () => {
    setIsUploadOpen(true);
  };

  // Send message and stream response
  const handleSendMessage = async (question: string) => {
    if (isStreaming) return;

    setErrorBanner(null);

    const targetSubjectId = activeSubjectId;
    if (!targetSubjectId) {
      setErrorBanner("Please create or select a subject before asking questions.");
      return;
    }

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: question,
      created_at: new Date().toISOString(),
    };

    const assistantPlaceholderId = `assistant-${Date.now()}`;
    const assistantMessage: Message = {
      id: assistantPlaceholderId,
      role: "assistant",
      content: "",
      mode: currentMode,
      isStreaming: true,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsStreaming(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let streamedText = "";
    let capturedSources: SourceCitation[] = [];

    await streamChat({
      question,
      subject_id: targetSubjectId,
      conversation_id: conversationId,
      mode: currentMode,
      signal: controller.signal,
      onMeta: (meta) => {
        setConversationId(meta.conversation_id);
      },
      onToken: (token) => {
        streamedText += token;
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantPlaceholderId
              ? { ...msg, content: streamedText }
              : msg
          )
        );
      },
      onSources: (sources) => {
        capturedSources = sources;
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantPlaceholderId
              ? { ...msg, sources }
              : msg
          )
        );
      },
      onDone: (data) => {
        setIsStreaming(false);
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantPlaceholderId
              ? { ...msg, content: data.text || streamedText, sources: capturedSources, isStreaming: false }
              : msg
          )
        );
      },
      onError: (err) => {
        setIsStreaming(false);
        setErrorBanner(err.message || "Failed to generate tutor answer");
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantPlaceholderId
              ? {
                  ...msg,
                  content:
                    streamedText ||
                    "I encountered an issue connecting to the tutoring engine. Please check that FastAPI is running.",
                  isStreaming: false,
                }
              : msg
          )
        );
      },
    });
  };

  // Stop generation
  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
      setMessages((prev) =>
        prev.map((msg) => (msg.isStreaming ? { ...msg, isStreaming: false } : msg))
      );
    }
  };

  // Click citation chip [S1], [S2]
  const handleCitationClick = (sourceId: string, sources?: SourceCitation[]) => {
    setSelectedSourceId(sourceId);
    if (sources && sources.length > 0) {
      setActiveSources(sources);
    }
    setIsSourceDrawerOpen(true);
  };

  // ── Authentication Barrier ──────────────────────────────────────────
  // If the user is not authenticated, show the Sign-In / Register screen.
  if (!token || !userEmail) {
    return <AuthScreen onAuthSuccess={handleAuthSuccess} />;
  }

  // ── Main Tutoring Application ──────────────────────────────────────
  return (
    <div className="app-container">
      {/* Mobile Sidebar Backdrop */}
      {isSidebarOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <Sidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        subjects={subjects}
        activeSubjectId={activeSubjectId}
        onSelectSubject={handleSelectSubject}
        onCreateSubject={handleCreateSubject}
        onDeleteSubject={handleDeleteSubject}
        onOpenUpload={handleOpenUpload}
        userEmail={userEmail}
        onOpenAuth={() => {}}
        onLogout={handleLogout}
      />

      {/* Main Stage */}
      <main className="main-stage">
        {/* Top bar */}
        <header className="top-bar">
          <div className="top-bar-left">
            <button
              type="button"
              className="mobile-menu-btn"
              onClick={() => setIsSidebarOpen(true)}
              aria-label="Open subjects menu"
            >
              <Menu size={20} />
            </button>
            <h1 className="active-subject-header">
              {activeSubject ? activeSubject.name : "Select a Subject"}
            </h1>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "0.85rem",
              color: "var(--text-secondary)",
              padding: "4px 10px",
              backgroundColor: "var(--bg-hover)",
              borderRadius: "var(--radius-sm)"
            }}>
              <User size={14} color="var(--color-brand)" />
              <span style={{ maxWidth: "150px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {userEmail}
              </span>
            </div>

            <button
              type="button"
              className="btn-secondary"
              onClick={handleOpenUpload}
              title="Upload and manage notes"
            >
              <UploadCloud size={15} />
              <span>Notes</span>
            </button>

            <button
              type="button"
              className="btn-secondary"
              onClick={handleLogout}
              title="Sign Out"
              style={{ color: "var(--color-danger)" }}
            >
              <LogOut size={15} />
              <span>Sign Out</span>
            </button>
          </div>
        </header>

        {/* Global error banner */}
        {errorBanner && (
          <div
            style={{
              backgroundColor: "var(--color-danger-bg)",
              color: "var(--color-danger)",
              padding: "8px 18px",
              fontSize: "0.85rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              borderBottom: "1px solid var(--border-subtle)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <AlertCircle size={16} />
              <span>{errorBanner}</span>
            </div>
            <button
              type="button"
              onClick={() => setErrorBanner(null)}
              aria-label="Dismiss error"
              style={{ color: "var(--color-danger)", fontWeight: "bold" }}
            >
              ×
            </button>
          </div>
        )}

        {/* Chat Window */}
        <ChatWindow
          messages={messages}
          isStreaming={isStreaming}
          activeSubjectName={activeSubject ? activeSubject.name : null}
          currentMode={currentMode}
          onModeChange={setCurrentMode}
          onSendMessage={handleSendMessage}
          onStopGeneration={handleStopGeneration}
          onCitationClick={handleCitationClick}
          onOpenUpload={handleOpenUpload}
          onCreateSubject={handleCreateSubject}
          onClearChat={() => {
            setMessages([]);
            setConversationId(null);
          }}
        />
      </main>

      {/* Upload Notes Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        subjectId={activeSubjectId}
        subjectName={activeSubject ? activeSubject.name : ""}
        subjects={subjects}
        onSelectSubject={handleSelectSubject}
        onCreateSubject={handleCreateSubject}
        onDocumentsUpdated={loadSubjects}
        onToast={addToast}
      />

      {/* Citation Inspector Drawer */}
      <SourceDrawer
        isOpen={isSourceDrawerOpen}
        onClose={() => setIsSourceDrawerOpen(false)}
        selectedSourceId={selectedSourceId}
        sources={activeSources}
      />

      {/* Floating Animated Toast Notifications */}
      <Toast toasts={toasts} onDismiss={removeToast} />
    </div>
  );
};

export default App;
