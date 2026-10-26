# AI Personal Tutor (RAG) — Complete Project Documentation

## 1. Project Overview & Objective

### Objective
The **AI Personal Tutor** is a multi-tenant, Retrieval-Augmented Generation (RAG) application engineered specifically for higher education and independent study. 

Standard commercial Large Language Models frequently fabricate facts, confuse course-specific notation, and lack visibility into specific lecture handouts or textbook versions. The primary objective of this project is to provide students with an intelligent, conversational study companion that:
1. **Grounds all explanations** strictly in the student's uploaded course documents (PDFs, Word docs, PowerPoint presentations, and notes).
2. **Eliminates hallucinations** by enforcing a strict relevance threshold and refusing out-of-context inquiries.
3. **Furnishes verifiable citations** (`[S1]`, `[S2]`) corresponding to exact slides and page numbers.
4. **Supports diverse pedagogical modalities** (e.g., standard academic exposition, analogies for novices, algorithmic step-by-step breakdowns, active recall practice quizzes, and guided Socratic inquiry).

---

## 2. System Architecture & Workflow

```
[User Document Upload] (PDF, DOCX, PPTX)
         │
         ▼
[Ingestion Pipeline] ───► Text Extraction & Sliding-Window Chunking (512 tokens, 64 overlap)
         │
         ▼
[Embedding Generation] ──► BAAI/bge-small-en-v1.5 (384-dimensional dense vectors)
         │
         ▼
[Storage Layer] ────────► Dual-Mode Database (SQLite for local demo / PostgreSQL 16 + pgvector for production)
```

### Retrieval & Generation Runtime Workflow

```
[Student Question + Chat History]
         │
         ▼
[Query Rewriter] ───────► Resolves ambiguous pronouns using chat context (with Fast-Path optimization)
         │
         ▼
[Hybrid Search Engine] ─► Dense Vector Similarity + Full-Text Keyword Search (BM25 / tsvector)
         │                Merged via Reciprocal Rank Fusion (RRF)
         ▼
[Cross-Encoder Reranker]► BAAI/bge-reranker-base computes deep query-passage cross-attention
         │
         ▼
[Relevance Filter] ─────► Filters out chunks below relevance threshold (score < 0.35)
         │
         ▼
[Multi-Provider LLM] ───► Streams response via Server-Sent Events (SSE) with inline [S1], [S2] tags
         │                (NVIDIA Nemotron / Groq LLaMA / Google Gemini / Anthropic Claude / Offline Engine)
         ▼
[Interactive React UI] ─► Markdown rendering, auto-scrolling, citation inspector drawer & copy actions
```

---

## 3. Technology Stack by Module

### A. Document Parsing & Ingestion Layer
* **PDF Extraction**: `PyMuPDF` (`fitz`) — preserves page indices and layout geometry.
* **Word Processing**: `python-docx` — parses structured paragraphs, headers, and bulleted lists.
* **PowerPoint Presentations**: `python-pptx` — extracts slide-by-slide text and preserves slide number metadata.
* **Chunking Engine**: Custom token-aware sliding window (~512 tokens with 64-token overlap) respecting paragraph boundaries and definitions.

### B. Machine Learning, Embedding & Reranking
* **Embedding Model**: `BAAI/bge-small-en-v1.5` (via `fastembed` / Hugging Face) producing normalized 384-dimensional vector embeddings.
* **Neural Reranker**: `BAAI/bge-reranker-base` (via `sentence-transformers` & PyTorch) — performs full bidirectional cross-attention over `(query, document)` pairs to eliminate irrelevant candidates before prompting the LLM.
* **Vector Mathematics**: Vectorized cosine similarity powered by `NumPy` dot-products in SQLite mode and `pgvector` HNSW indexes in PostgreSQL mode.

### C. Language Model Providers & Orchestration
* **NVIDIA Inference Microservices (NIM)**: `nvidia/nemotron-3.5-lightning-30b-a3b` with reasoning stream separation.
* **Groq Cloud API**: `llama-3.3-70b-versatile` for high-throughput generation.
* **Google Gemini API**: `gemini-1.5-flash` via official `google-generativeai` SDK.
* **Anthropic API**: `claude-3-5-sonnet` for pedagogical decomposition.
* **Local Extractive Fallback**: Offline heuristic engine utilizing TF-IDF, bigram matching, and definition-indicator heuristics.

### D. Backend Web API & Authentication
* **Web Framework**: Python 3.11 + `FastAPI` (asynchronous ASGI architecture).
* **Server**: `Uvicorn` with reload capabilities.
* **Validation**: `Pydantic v2` and `pydantic-settings`.
* **Security & Auth**: JWT (JSON Web Tokens) cryptographically signed via `HMAC-SHA256`, password hashing using `PBKDF2-HMAC-SHA256` (100,000 rounds with random cryptographic salt).
* **Streaming Protocol**: HTTP Server-Sent Events (`text/event-stream`) delivering real-time tokens, source citations, and metadata.

### E. Frontend User Interface
* **Framework**: React 18 + TypeScript + Vite.
* **Styling & Design System**: Tailwind CSS + custom CSS variables (academic typography and accessible contrast).
* **Icons**: `lucide-react`.
* **Markdown & Math**: `react-markdown` with syntax highlighting and LaTeX equation support.
* **State Management**: Reactive custom hooks (`useStreamingChat`, `useSubjects`) with `localStorage` token persistence.
* **Authentication UI**: Modal dialog with tabbed Sign In / Sign Up, email validation, and automatic session switching.

---

## 4. User Accounts & Authentication

The application features full user account management:
1. **Registration**: Creates a secure user profile (`/auth/register`) storing salted PBKDF2 password hashes in the database.
2. **Sign In**: Authenticates credentials (`/auth/login`) and issues an HTTP Bearer JWT token valid for session persistence.
3. **Data Isolation**: All subjects, uploaded notes, and conversations are strictly isolated to the authenticated `user_id`.
4. **Guest / Demo Mode**: If no token is provided, the platform automatically defaults to a sandbox user account (`00000000-0000-0000-0000-000000000001`) with sample notes pre-loaded.

---

## 5. Pedagogical Tutoring Modes

| Mode | Educational Objective | Prompt Strategy |
| :--- | :--- | :--- |
| **Explain** | Comprehensive, structured academic explanation | Grounded summary with definitions and source cross-references |
| **ELI5** | Intuitive conceptual grasping for beginners | Relatable everyday analogies avoiding dense technical jargon |
| **Step-by-Step** | Methodical problem solving and mathematical derivations | Numbered, progressive stages with explicit justifications |
| **Practice Quiz** | Active recall and self-assessment | Generates multiple-choice and conceptual questions from lecture notes |
| **Socratic** | Critical thinking and guided self-discovery | Poses thought-provoking questions and hints rather than direct answers |

---

## 6. How to Run & Test the Application

### 1. Backend Server (Port 8000)
```powershell
$env:PYTHONPATH="C:\Users\sathy\OneDrive\Desktop\Ai personal tutor rag project\backend"
python -m uvicorn app.main:app --app-dir "C:\Users\sathy\OneDrive\Desktop\Ai personal tutor rag project\backend" --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend Client (Port 3000)
```powershell
cd "C:\Users\sathy\OneDrive\Desktop\Ai personal tutor rag project\frontend"
npm run preview -- --port 3000 --host 127.0.0.1
```

### 3. Access in Browser
Visit **`http://127.0.0.1:3000`** in your browser to sign in, upload notes, and test the AI Personal Tutor.
