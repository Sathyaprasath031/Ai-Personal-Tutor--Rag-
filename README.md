# AI Personal Tutor (RAG)

A RAG-powered personal tutor that lets students upload their notes and PDFs, organised by subject, and get tutor-style explanations grounded in their own content with page-level citations.

## Tech Stack

- **Backend:** Python 3.11, FastAPI, Redis + RQ worker
- **Database:** PostgreSQL 16 with pgvector and full-text search
- **Parsing:** PyMuPDF, python-docx, python-pptx, Tesseract OCR fallback
- **Retrieval:** Hybrid search (vector + keyword), RRF fusion, cross-encoder reranker
- **Embeddings/Reranker:** `BAAI/bge-small-en-v1.5` and `BAAI/bge-reranker-base` (local)
- **LLM:** NVIDIA NEMOTRON API (model configurable via `.env`)
- **Infra:** Docker Compose (db, redis, api, worker)
- **Frontend:** React 18 (Vite + TypeScript)

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- An [Anthropic API key](https://console.anthropic.com/)

## Quick Start

### 1. Clone and configure

```bash
git clone <repo-url>
cd "Rag Personal Tutor"

# Copy the env template and add your Anthropic API key
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 2. Start Services

You can run the full system using **Docker Compose** (recommended for production) or **Standalone Local** (no Docker required).

#### Option A: Docker Compose (All services)
```bash
docker compose up --build
```
This starts four services:
| Service | Port | Description |
|---------|------|-------------|
| `db`    | 5432 | PostgreSQL 16 + pgvector (schema auto-applied) |
| `redis` | 6379 | Redis 7 (job queue) |
| `api`   | 8000 | FastAPI backend (hot-reload enabled) |
| `worker`| —    | RQ worker processing ingestion jobs |

#### Option B: Standalone Local (No Docker required)
The backend includes an automatic embedded SQLite + NumPy vector search and in-process background worker fallback if PostgreSQL/Redis are offline:
```bash
# Terminal 1: Start backend
python -m uvicorn app.main:app --port 8000

# Terminal 2: Start frontend
cd frontend
npm run dev
```

### 3. Start the Frontend
```bash
cd frontend
npm install
npm run dev
```
The React app runs at **http://localhost:3000** and talks to the API at `http://localhost:8000`.

### 4. Verify

- Health check: [http://localhost:8000/health](http://localhost:8000/health)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Frontend: [http://localhost:3000](http://localhost:3000)
- End-to-end verification script: `python eval/verify_e2e.py`

## Usage

1. **Create a subject** (e.g. "Physics", "DBMS") in the sidebar
2. **Upload PDF/DOCX/PPTX/TXT/MD** files — watch status go from `queued` → `processing` → `ready`
3. **Ask questions** — the tutor streams a cited answer grounded in your notes
4. **Click citations** like `[S1]` to see the source file, page range, and snippet
5. **Switch modes** — Explain, ELI5, Step-by-step, Quiz me, Socratic

## Project Structure

```
├── docker-compose.yml          # All services
├── .env.example                # Environment template
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── db/schema.sql           # PostgreSQL DDL (auto-applied on first run)
│   └── app/
│       ├── main.py             # FastAPI routes
│       ├── config.py           # Settings from .env
│       ├── db.py               # Connection pool
│       ├── auth.py             # Auth stub (demo user)
│       ├── worker.py           # RQ worker entrypoint
│       ├── ingestion/          # Parse → chunk → embed → store
│       └── rag/                # Rewrite → retrieve → rerank → answer
├── frontend/                   # Vite + React 18
├── eval/                       # Retrieval evaluation scripts
└── docs/                       # Architecture & implementation docs
```

## Development

### Rebuild after code changes
```bash
docker compose up --build
```

### View logs
```bash
docker compose logs -f api worker
```

### Reset database
```bash
docker compose down -v   # removes volumes (all data)
docker compose up --build
```

### Run tests
```bash
docker compose exec api pytest tests/ -v
```

## Environment Variables

See [`.env.example`](.env.example) for all available settings. Key ones:

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (required) |
| `LLM_MODEL` | Claude model for answers (default: `claude-sonnet-4-20250514`) |
| `REWRITE_MODEL` | Claude model for query rewriting (default: `claude-haiku-4-20250414`) |
| `RELEVANCE_THRESHOLD` | Min reranker score to use a chunk (default: `0.15`) |

## License

Private — for educational use.
