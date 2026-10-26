import { Subject, DocumentItem } from "../types";

const getApiBase = () => {
  if (typeof window !== "undefined") {
    const host = window.location.hostname || "127.0.0.1";
    return `http://${host}:8000`;
  }
  return "http://127.0.0.1:8000";
};

const API_BASE = import.meta.env.VITE_API_URL || getApiBase();

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  options.headers = {
    ...getAuthHeader(),
    ...options.headers,
  };
  try {
    const res = await fetch(url, options);
    if (!res.ok) {
      let detail = `Request failed (${res.status})`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) {
          detail = typeof errorJson.detail === "string" ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fallback to status text
        detail = res.statusText || detail;
      }
      throw new Error(detail);
    }
    return (await res.json()) as T;
  } catch (err: any) {
    if (err.name === "TypeError" && err.message.includes("fetch")) {
      throw new Error(`Cannot reach backend server at ${API_BASE}. Ensure FastAPI is running.`);
    }
    throw err;
  }
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
  full_name?: string;
}

export const api = {
  // Authentication
  async register(email: string, password: string, fullName?: string): Promise<AuthResponse> {
    return request<AuthResponse>("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, full_name: fullName }),
    });
  },

  async login(email: string, password: string): Promise<AuthResponse> {
    return request<AuthResponse>("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  },

  // Subjects
  async getSubjects(): Promise<Subject[]> {
    return request<Subject[]>("/subjects");
  },

  async createSubject(name: string): Promise<Subject> {
    return request<Subject>("/subjects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
  },

  async deleteSubject(id: string): Promise<{ deleted: string }> {
    return request<{ deleted: string }>(`/subjects/${id}`, {
      method: "DELETE",
    });
  },

  // Documents
  async getDocuments(subjectId?: string): Promise<DocumentItem[]> {
    const query = subjectId ? `?subject_id=${encodeURIComponent(subjectId)}` : "";
    return request<DocumentItem[]>(`/documents${query}`);
  },

  async uploadDocument(subjectId: string, file: File): Promise<{ id: string; status: string }> {
    const formData = new FormData();
    formData.append("subject_id", subjectId);
    formData.append("file", file);

    return request<{ id: string; status: string }>("/documents", {
      method: "POST",
      body: formData,
    });
  },

  async deleteDocument(id: string): Promise<{ deleted: string }> {
    return request<{ deleted: string }>(`/documents/${id}`, {
      method: "DELETE",
    });
  },
};
