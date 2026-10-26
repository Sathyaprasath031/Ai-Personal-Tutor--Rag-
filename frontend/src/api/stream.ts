import { SourceCitation, TutorMode } from "../types";

const getApiBase = () => {
  if (typeof window !== "undefined") {
    const host = window.location.hostname || "127.0.0.1";
    return `http://${host}:8000`;
  }
  return "http://127.0.0.1:8000";
};

const API_BASE = import.meta.env.VITE_API_URL || getApiBase();

export interface StreamChatOptions {
  question: string;
  subject_id?: string | null;
  conversation_id?: string | null;
  mode?: TutorMode;
  signal?: AbortSignal;
  onMeta?: (meta: { conversation_id: string }) => void;
  onToken: (token: string) => void;
  onSources: (sources: SourceCitation[]) => void;
  onDone: (data: { text: string }) => void;
  onError: (err: Error) => void;
}

export async function streamChat(options: StreamChatOptions): Promise<void> {
  const {
    question,
    subject_id,
    conversation_id,
    mode = "explain",
    signal,
    onMeta,
    onToken,
    onSources,
    onDone,
    onError,
  } = options;

    const token = localStorage.getItem("token");
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: "POST",
      headers,
      body: JSON.stringify({
        question,
        subject_id: subject_id || null,
        conversation_id: conversation_id || null,
        mode,
      }),
      signal,
    });

    if (!response.ok) {
      let message = `Chat failed (${response.status})`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail) {
          message = errorJson.detail;
        }
      } catch {
        message = response.statusText || message;
      }
      throw new Error(message);
    }

    if (!response.body) {
      throw new Error("ReadableStream not supported on this browser.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      // Split SSE packets delimited by double newline
      const packets = buffer.split("\n\n");
      // The last element is either empty (if ended on \n\n) or incomplete chunk
      buffer = packets.pop() || "";

      for (const packet of packets) {
        if (!packet.trim()) continue;

        let eventType = "message";
        let dataStr = "";

        const lines = packet.split("\n");
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.replace("event: ", "").trim();
          } else if (line.startsWith("data: ")) {
            dataStr = line.replace("data: ", "").trim();
          }
        }

        if (!dataStr) continue;

        try {
          const parsedData = JSON.parse(dataStr);
          if (eventType === "meta" && onMeta) {
            onMeta(parsedData);
          } else if (eventType === "token") {
            onToken(parsedData);
          } else if (eventType === "sources") {
            onSources(parsedData);
          } else if (eventType === "done") {
            onDone(parsedData);
          }
        } catch (parseError) {
          console.warn("Failed to parse SSE JSON payload:", dataStr, parseError);
        }
      }
    }
  } catch (err: any) {
    if (err.name === "AbortError") {
      // User cancelled generation — gracefully notify
      return;
    }
    onError(err);
  }
}
