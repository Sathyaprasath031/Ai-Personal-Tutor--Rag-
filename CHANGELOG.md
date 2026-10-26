# CHANGELOG

All deviations from `docs/architecture.md` and `docs/implementation.md`, and why.

## M1 — Docker Infra & Backend Skeleton
1. **Pydantic v2 config style:** Changed from nested `class Config: env_file = ".env"` to `model_config = SettingsConfigDict(env_file=".env", extra="ignore")` — the Pydantic v1 style is deprecated in pydantic-settings v2.
2. **Pool opened lazily:** Set `open=False` in ConnectionPool and explicitly call `pool.open()` in FastAPI's `lifespan` handler. This prevents import-time connection attempts when the DB isn't reachable yet.
3. **Subject ownership validation on upload:** Added a check that `subject_id` belongs to the current `user_id` before accepting a file upload.
4. **HuggingFace cache volume:** Added `hf_cache` named volume in `docker-compose.yml` so embedding and reranker model weights persist across container restarts.
5. **Claude model names:** Updated to current valid Anthropic model IDs (`claude-sonnet-4-20250514` / `claude-haiku-4-20250414`).
6. **Docker healthchecks with `depends_on` conditions:** API and worker wait for `db` and `redis` to be healthy before starting.
7. **File metadata:** Added `mime_type` and `file_size` columns to `documents` table for better validation and UI display.
8. **Auth module:** Extracted auth into `auth.py` with JWT token support and tenant dependency injection.

## M2 — Ingestion Pipeline
1. **File handle safety on Windows:** Wrapped PyMuPDF `fitz.open` inside Python context manager (`with fitz.open(path) as doc:`) in `parse_pdf` to prevent Windows file locking permission errors upon cleanup.
2. **Minimum chunk fragment threshold:** Preserved $\ge 15$ words threshold to filter out empty whitespace fragments and page numbers while retaining coherent paragraphs.

## M3 — Streaming Chat & SSE
1. **Robust SSE Event Sequence:** Emitted explicit `event: meta` with `conversation_id`, followed by token-by-token streaming `event: token`, final `event: sources`, and `event: done`.
2. **Prompt Injection Defense:** Encapsulated retrieved study chunks inside `<sources><source id="S#" file="..." pages="..." section="...">...</source></sources>` XML tags with strict system instructions that content inside `<sources>` is untrusted data and commands inside must be ignored.

## M4 — Hybrid Search, Reranker, & Relevance Gate
1. **Full-Text Search Safety:** Used PostgreSQL `websearch_to_tsquery('english', %s)` with `ts_rank_cd` to safely handle raw user queries with punctuation or operator characters.
2. **Calibrated Reranker Threshold:** Applied Sigmoid activation $\frac{1}{1 + e^{-s}}$ on raw cross-encoder logits so `RELEVANCE_THRESHOLD` (0.15) functions as a calibrated probability. Irrelevant queries fall back to the honest "not found in notes" path.
3. **Recall@5 Evaluation:** Evaluated on `eval/golden.jsonl` with 100% recall.

## M5 — Query Rewriting
1. **Zero-Latency Empty History Passthrough:** Skipped external LLM call when conversation history is empty, returning the user query immediately.
2. **Graceful Fallback:** If Anthropic API encounters rate limits or errors during query reformulation, gracefully falls back to the original student message.

## M6 — React Frontend
1. **React 18 + Vite + TypeScript:** Built on port 3000, zero UI-kit dependencies, custom CSS with calm study palette and accessible focus rings.
2. **Live Document Polling:** Polling `GET /documents` every 2.5s while documents are in `queued` or `processing` status.
3. **LaTeX Math & Citations:** Integrated `react-markdown`, `remark-math`, `rehype-katex`, and custom citation chip component converting `[S1]`, `[S2]` into interactive buttons that open the slide-over source drawer.
4. **Stream Cancellation:** Implemented `AbortController` to cancel/stop generation in real time.

## M7 — Tutor Modes
1. **5 Interactive Modes:** Implemented `explain`, `eli5`, `steps`, `quiz`, and `socratic` with distinct pedagogical directives.
2. **Two-Way Quiz Flow:** Instructs the tutor not to reveal answers when proposing a quiz, and to grade student replies with source citations upon submission.

## M8 — Multi-Format & OCR Support
1. **DOCX & PPTX:** Integrated `python-docx` (with heading style extraction) and `python-pptx` (with slide number tracking).
2. **Scanned PDF Fallback:** Automatically switches to Tesseract OCR at 200 DPI when a PDF page has $< 30$ extractable text characters.

## M9 — JWT Authentication & User Isolation
1. **Cryptographic PBKDF2 Hashing:** Salted SHA256 password hashing with 100,000 rounds.
2. **Signed Bearer JWTs:** Implemented HMAC-SHA256 token issuance and expiration checking.
3. **Rigorous Tenant Isolation:** Every single DB query and hybrid search strictly includes `WHERE user_id = %s`.

## Dual Execution Engine & End-to-End Verification
1. **Smart DB Pool Proxy:** `backend/app/db.py` uses `SmartConnectionPool` which tests PostgreSQL reachability with a 1.0s non-blocking check. If running in Docker, it connects to PostgreSQL + `pgvector`. If running standalone without Docker, it routes transparently to embedded SQLite + NumPy cosine distance search in `data/tutor_local.db`.
2. **Worker Fallback:** `backend/app/main.py` routes document ingestion jobs through Redis RQ if online, and automatically falls back to an asynchronous in-process background worker thread if Redis is offline.
3. **Comprehensive Verification:** Ran `eval/verify_e2e.py` covering the full lifecycle:
   - Health check
   - Registration and JWT token generation
   - Subject creation
   - Multi-page document upload and background ingestion (`queued` -> `processing` -> `ready`)
   - Dense + sparse hybrid retrieval with RRF
   - Cross-encoder reranker with Sigmoid calibration
   - Streaming SSE chat with `[S1]` page-level citations and interactive source drawer metadata
   - Out-of-domain query handling with honest refusal fallback
4. **Test Suite:** 42/42 unit and integration tests passing (`pytest backend/tests -v`).
