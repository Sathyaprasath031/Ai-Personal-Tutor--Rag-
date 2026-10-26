import React, { useRef, useEffect, useState } from "react";
import { ArrowUp, Square, Sparkles, BookOpen, User, RotateCcw, Zap, ArrowDown, Copy, Check } from "lucide-react";
import { Message, SourceCitation, TutorMode } from "../types";
import { MarkdownMessage } from "./MarkdownMessage";
import { ModeSelector } from "./ModeSelector";

interface ChatWindowProps {
  messages: Message[];
  isStreaming: boolean;
  activeSubjectName: string | null;
  currentMode: TutorMode;
  onModeChange: (mode: TutorMode) => void;
  onSendMessage: (question: string) => void;
  onStopGeneration: () => void;
  onCitationClick: (sourceId: string, sources?: SourceCitation[]) => void;
  onOpenUpload: () => void;
  onClearChat: () => void;
  onCreateSubject?: (name: string) => void;
}

const STARTER_PROMPTS = [
  { label: "Exam Cheat Sheet", prompt: "Chunk this topic into an exam study guide: key formulas, main takeaways, and common traps." },
  { label: "Practice Quiz", prompt: "Give me a 3-question conceptual practice quiz based on my notes." },
  { label: "ELI5 Concept", prompt: "Break down the hardest concept from my uploaded notes into a simple analogy." },
  { label: "Step-by-Step Derivation", prompt: "Walk me step-by-step through the core process or derivation in my notes." },
];

export const ChatWindow: React.FC<ChatWindowProps> = ({
  messages,
  isStreaming,
  activeSubjectName,
  currentMode,
  onModeChange,
  onSendMessage,
  onStopGeneration,
  onCitationClick,
  onOpenUpload,
  onClearChat,
  onCreateSubject,
}) => {
  const [inputText, setInputText] = useState("");
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const chatContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isAutoScrollActive = useRef(true);

  // Monitor user scrolling: pause auto-scroll if user scrolled up to read
  const handleScroll = () => {
    if (!chatContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
    const distFromBottom = scrollHeight - scrollTop - clientHeight;
    const isNearBottom = distFromBottom < 100;
    isAutoScrollActive.current = isNearBottom;
    setShowScrollBottom(!isNearBottom && messages.length > 0);
  };

  // Auto-scroll when near bottom
  useEffect(() => {
    if (isAutoScrollActive.current && chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: isStreaming ? "auto" : "smooth",
      });
    }
  }, [messages, isStreaming]);

  const scrollToBottom = () => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: "smooth",
      });
      isAutoScrollActive.current = true;
      setShowScrollBottom(false);
    }
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    const trimmed = inputText.trim();
    if (!trimmed || isStreaming) return;
    isAutoScrollActive.current = true;
    onSendMessage(trimmed);
    setInputText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleTextareaInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputText(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`;
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", width: "100%", overflow: "hidden", position: "relative" }}>
      {/* Scrollable chat thread */}
      <div
        ref={chatContainerRef}
        className="chat-container"
        onScroll={handleScroll}
      >
        {messages.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">
              <Sparkles size={26} />
            </div>
            <h2 className="empty-state-title">
              {activeSubjectName ? `Tutor ready for ${activeSubjectName}` : "What would you like to learn today?"}
            </h2>
            <p className="empty-state-desc">
              Ask questions directly from your uploaded course materials. Every explanation is strictly grounded with verifiable slide and page citations.
            </p>

            {/* Quick action buttons */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", justifyContent: "center", marginTop: "4px" }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={onOpenUpload}
                style={{ padding: "8px 16px", borderRadius: "var(--radius-full)" }}
              >
                <BookOpen size={15} />
                <span>Manage Course Notes</span>
              </button>
            </div>

            {/* Starter Questions in Modern ChatGPT Grid */}
            <div style={{ width: "100%", maxWidth: "640px", marginTop: "16px" }}>
              <div
                className="starter-cards-grid"
                style={{
                  display: "grid",
                  gap: "12px",
                  width: "100%"
                }}
              >
                {STARTER_PROMPTS.map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      isAutoScrollActive.current = true;
                      onSendMessage(item.prompt);
                    }}
                    style={{
                      textAlign: "left",
                      padding: "14px 16px",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid var(--border-subtle)",
                      backgroundColor: "var(--bg-surface)",
                      cursor: "pointer",
                      fontSize: "0.85rem",
                      display: "flex",
                      flexDirection: "column",
                      gap: "6px",
                      minWidth: 0,
                      width: "100%",
                      boxSizing: "border-box",
                      transition: "all var(--transition-fast)",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = "var(--border-strong)";
                      e.currentTarget.style.backgroundColor = "var(--bg-surface-hover)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = "var(--border-subtle)";
                      e.currentTarget.style.backgroundColor = "var(--bg-surface)";
                    }}
                  >
                    <span style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: "0.88rem" }}>
                      {item.label}
                    </span>
                    <span style={{
                      fontSize: "0.78rem",
                      color: "var(--text-muted)",
                      lineHeight: 1.45,
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      wordBreak: "break-word"
                    }}>
                      {item.prompt}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="chat-thread">
            {messages.map((msg) => {
              const isUser = msg.role === "user";
              return (
                <div key={msg.id} className={`message-row ${isUser ? "user" : "assistant"}`}>
                  <div className={`message-bubble ${isUser ? "user" : "assistant"}`}>
                    <div className="message-header">
                      <span style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 600 }}>
                        {isUser ? (
                          <div style={{ width: "22px", height: "22px", borderRadius: "50%", backgroundColor: "rgba(255,255,255,0.1)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                            <User size={13} />
                          </div>
                        ) : (
                          <div style={{ width: "22px", height: "22px", borderRadius: "50%", backgroundColor: "var(--color-brand)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                            <Sparkles size={13} color="#ffffff" />
                          </div>
                        )}
                        <span style={{ color: "var(--text-primary)" }}>{isUser ? "You" : "Tutor"}</span>
                      </span>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        {!isUser && msg.mode && (
                          <span className="message-mode-badge">{msg.mode}</span>
                        )}
                        {!isUser && msg.content && (
                          <button
                            type="button"
                            className="copy-btn"
                            onClick={() => handleCopy(msg.id, msg.content)}
                            title="Copy answer"
                            aria-label="Copy answer"
                          >
                            {copiedId === msg.id ? (
                              <>
                                <Check size={12} color="var(--color-brand)" />
                                <span style={{ color: "var(--color-brand)" }}>Copied</span>
                              </>
                            ) : (
                              <>
                                <Copy size={12} />
                                <span>Copy</span>
                              </>
                            )}
                          </button>
                        )}
                      </div>
                    </div>

                    <div style={{ marginTop: "4px" }}>
                      {isUser ? (
                        <p style={{ whiteSpace: "pre-wrap" }}>{msg.content}</p>
                      ) : msg.content ? (
                        <MarkdownMessage
                          content={msg.content}
                          onCitationClick={(id) => onCitationClick(id, msg.sources)}
                        />
                      ) : (
                        <div style={{ display: "flex", alignItems: "center", gap: "5px", padding: "8px 0" }}>
                          <span className="typing-dot" />
                          <span className="typing-dot" />
                          <span className="typing-dot" />
                          <span style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginLeft: "6px" }}>
                            Searching notes & formulating response...
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Floating Scroll-to-Bottom Pill Button */}
      {showScrollBottom && (
        <button
          type="button"
          className="scroll-bottom-btn"
          onClick={scrollToBottom}
          title="Scroll to latest message"
          aria-label="Scroll to bottom"
        >
          <ArrowDown size={14} />
          <span>New messages</span>
        </button>
      )}

      {/* ChatGPT-style Floating Input Pill */}
      <div className="input-dock">
        <div className="input-container">
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            placeholder={
              activeSubjectName
                ? `Message your tutor about ${activeSubjectName}...`
                : "Ask anything about your course materials..."
            }
            value={inputText}
            onChange={handleTextareaInput}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
            rows={1}
            aria-label="Message your tutor"
          />

          <div className="input-actions">
            <ModeSelector
              currentMode={currentMode}
              onChange={onModeChange}
              disabled={isStreaming}
            />

            <div className="input-actions-right">
              {messages.length > 0 && !isStreaming && (
                <button
                  type="button"
                  onClick={onClearChat}
                  title="Clear conversation"
                  aria-label="Clear conversation"
                  style={{ color: "var(--text-muted)", padding: "4px" }}
                >
                  <RotateCcw size={16} />
                </button>
              )}

              {isStreaming ? (
                <button
                  type="button"
                  className="stop-button"
                  onClick={onStopGeneration}
                  title="Stop generating"
                  aria-label="Stop generating"
                >
                  <Square size={14} fill="currentColor" />
                </button>
              ) : (
                <button
                  type="button"
                  className="send-button"
                  onClick={handleSend}
                  disabled={!inputText.trim()}
                  title="Send message"
                  aria-label="Send message"
                >
                  <ArrowUp size={16} strokeWidth={2.5} />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
