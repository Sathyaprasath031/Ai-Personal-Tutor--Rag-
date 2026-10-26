export type TutorMode = "explain" | "eli5" | "steps" | "quiz" | "summary" | "socratic";

export interface Subject {
  id: string;
  name: string;
  created_at: string;
  document_count?: number;
}

export type DocumentStatus = "queued" | "processing" | "ready" | "failed";

export interface DocumentItem {
  id: string;
  subject_id: string;
  filename: string;
  status: DocumentStatus;
  error?: string | null;
  pages?: number | null;
  file_size?: number | null;
  created_at: string;
}

export interface SourceCitation {
  id: string; // e.g., "S1"
  filename: string;
  page_start: number;
  page_end: number;
  section: string;
  snippet: string;
  score?: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  mode?: TutorMode;
  sources?: SourceCitation[];
  created_at?: string;
  isStreaming?: boolean;
}
