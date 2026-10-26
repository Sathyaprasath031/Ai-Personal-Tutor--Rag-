import json
import logging
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from redis import Redis
from rq import Queue

from .config import settings
from .db import pool
from .auth import get_current_user_id, hash_password, verify_password, create_access_token
from .rag.answer import answer_stream

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager


# ── Lifecycle ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        pool.open()
        logger.info("Database connection pool opened")
    except Exception as e:
        logger.warning("Could not open DB pool at startup: %s", e)
    yield
    try:
        pool.close()
        logger.info("Database connection pool closed")
    except Exception as e:
        logger.warning("Error closing DB pool: %s", e)


# ── FastAPI app ──────────────────────────────────────────────
app = FastAPI(title="AI Personal Tutor", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Redis queue ──────────────────────────────────────────────
redis_conn = Redis.from_url(settings.redis_url)
queue = Queue("ingest", connection=redis_conn)

# ── Constants ────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md"}
MAX_FILE_SIZE_MB = 50


# ── Health ───────────────────────────────────────────────────
@app.get("/health")
def health():
    db_ok = False
    redis_ok = False
    try:
        with pool.connection() as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except Exception as e:
        logger.warning("DB health check failed: %s", e)
    try:
        redis_conn.ping()
        redis_ok = True
    except Exception as e:
        logger.debug("Redis health check note: %s", e)
    return {
        "status": "healthy" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "offline",
    }


# ── Authentication ───────────────────────────────────────────
class AuthCredentials(BaseModel):
    email: str
    password: str


@app.post("/auth/register", status_code=201)
def register(body: AuthCredentials):
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Valid email is required")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    hashed = hash_password(body.password)
    try:
        with pool.connection() as conn:
            row = conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
                (email, hashed),
            ).fetchone()
            user_id = str(row[0])
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(400, "Email is already registered")
        raise HTTPException(500, f"Registration failed: {exc}")

    token = create_access_token(user_id, email)
    return {"access_token": token, "token_type": "bearer", "user_id": user_id, "email": email}


@app.post("/auth/login")
def login(body: AuthCredentials):
    email = body.email.strip().lower()
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = %s",
            (email,),
        ).fetchone()

    if not row or not row[1] or not verify_password(body.password, row[1]):
        raise HTTPException(401, "Invalid email or password")

    user_id = str(row[0])
    token = create_access_token(user_id, email)
    return {"access_token": token, "token_type": "bearer", "user_id": user_id, "email": email}


# ── Subjects ─────────────────────────────────────────────────
class SubjectCreate(BaseModel):
    name: str


@app.post("/subjects", status_code=201)
def create_subject(body: SubjectCreate, user_id: str = Depends(get_current_user_id)):
    with pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO subjects (user_id, name) VALUES (%s, %s) RETURNING id, name, created_at",
            (user_id, body.name.strip()),
        ).fetchone()
    created_str = row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2])
    return {"id": str(row[0]), "name": row[1], "created_at": created_str}


@app.get("/subjects")
def list_subjects(user_id: str = Depends(get_current_user_id)):
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT id, name, created_at FROM subjects WHERE user_id = %s ORDER BY created_at",
            (user_id,),
        ).fetchall()

    return [
        {"id": str(r[0]), "name": r[1], "created_at": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2])}
        for r in rows
    ]


@app.delete("/subjects/{subject_id}")
def delete_subject(subject_id: str, user_id: str = Depends(get_current_user_id)):
    with pool.connection() as conn:
        row = conn.execute(
            "DELETE FROM subjects WHERE id = %s AND user_id = %s RETURNING id",
            (subject_id, user_id),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Subject not found")
    return {"deleted": str(row[0])}


# ── Documents ────────────────────────────────────────────────
@app.post("/documents", status_code=201)
async def upload_document(
    subject_id: str = Form(...),
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    # Validate extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Read and validate size
    data = await file.read()
    if len(data) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {MAX_FILE_SIZE_MB} MB limit")

    # Verify subject belongs to user
    with pool.connection() as conn:
        subj = conn.execute(
            "SELECT id FROM subjects WHERE id = %s AND user_id = %s",
            (subject_id, user_id),
        ).fetchone()
    if not subj:
        raise HTTPException(404, "Subject not found")

    # Save file
    doc_id = str(uuid.uuid4())
    user_dir = Path(settings.upload_dir) / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    file_path = user_dir / f"{doc_id}{ext}"
    file_path.write_bytes(data)

    # Insert DB record
    with pool.connection() as conn:
        conn.execute(
            """INSERT INTO documents (id, user_id, subject_id, filename, file_path, mime_type, file_size)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (doc_id, user_id, subject_id, file.filename, str(file_path), file.content_type, len(data)),
        )

    # Enqueue ingestion job (Redis RQ with fallback to background thread)
    try:
        queue.enqueue("app.ingestion.pipeline.ingest_document", doc_id, job_timeout=1800)
        logger.info(f"Document {doc_id} queued for ingestion via Redis RQ")
    except Exception as exc:
        logger.warning(f"Redis queue unavailable ({exc}), running ingestion in background thread")
        from .ingestion.pipeline import ingest_document
        import threading
        threading.Thread(target=ingest_document, args=(doc_id,), daemon=True).start()

    return {"id": doc_id, "filename": file.filename, "status": "queued"}


@app.get("/documents")
def list_documents(
    subject_id: str | None = Query(None),
    user_id: str = Depends(get_current_user_id),
):
    sql = """SELECT id, subject_id, filename, status, error, page_count, file_size, created_at
             FROM documents WHERE user_id = %s"""
    params: list = [user_id]
    if subject_id:
        sql += " AND subject_id = %s"
        params.append(subject_id)
    sql += " ORDER BY created_at DESC"

    with pool.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        {
            "id": str(r[0]),
            "subject_id": str(r[1]),
            "filename": r[2],
            "status": r[3],
            "error": r[4],
            "pages": r[5],
            "file_size": r[6],
            "created_at": r[7].isoformat() if hasattr(r[7], "isoformat") else str(r[7]),
        }
        for r in rows
    ]


@app.delete("/documents/{doc_id}")
def delete_document(
    doc_id: str,
    user_id: str = Depends(get_current_user_id),
):
    with pool.connection() as conn:
        row = conn.execute(
            "DELETE FROM documents WHERE id = %s AND user_id = %s RETURNING file_path",
            (doc_id, user_id),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    file_path = row[0]
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
    return {"deleted": doc_id}


# ── Chat (Streaming RAG Tutor) ──────────────────────────────
class ChatRequest(BaseModel):
    question: str
    subject_id: str | None = None
    conversation_id: str | None = None
    mode: str = "explain"  # explain | eli5 | steps | quiz | socratic


@app.post("/chat")
def chat(
    body: ChatRequest,
    user_id: str = Depends(get_current_user_id),
):

    with pool.connection() as conn:
        conv_id = body.conversation_id
        if not conv_id:
            row = conn.execute(
                """INSERT INTO conversations (user_id, subject_id, title)
                   VALUES (%s, %s, %s) RETURNING id""",
                (user_id, body.subject_id, body.question[:60]),
            ).fetchone()
            conv_id = str(row[0])

        # Fetch prior messages in this conversation (up to last 6)
        rows = conn.execute(
            """SELECT role, content FROM messages
               WHERE conversation_id = %s
               ORDER BY id DESC LIMIT 6""",
            (conv_id,),
        ).fetchall()
        history = [{"role": r[0], "content": r[1]} for r in reversed(rows)]

        # Record the student's question
        conn.execute(
            """INSERT INTO messages (conversation_id, role, content, mode)
               VALUES (%s, 'user', %s, %s)""",
            (conv_id, body.question, body.mode),
        )

    def event_stream():
        final_text = ""
        sources: list = []

        # 1. Emit metadata event with conversation_id
        yield f"event: meta\ndata: {json.dumps({'conversation_id': conv_id})}\n\n"

        # 2. Stream generation events
        for chunk in answer_stream(
            user_id=user_id,
            question=body.question,
            history=history,
            subject_id=body.subject_id,
            mode=body.mode,
        ):
            if chunk.startswith("event: sources"):
                try:
                    data_str = chunk.split("data: ", 1)[1].strip()
                    sources = json.loads(data_str)
                except Exception as e:
                    logger.warning("Failed to parse sources event: %s", e)
            elif chunk.startswith("event: done"):
                try:
                    data_str = chunk.split("data: ", 1)[1].strip()
                    final_text = json.loads(data_str).get("text", "")
                except Exception as e:
                    logger.warning("Failed to parse done event: %s", e)

            yield chunk

        # 3. Store the assistant's reply and cited sources in DB
        try:
            with pool.connection() as conn:
                conn.execute(
                    """INSERT INTO messages (conversation_id, role, content, mode, sources)
                       VALUES (%s, 'assistant', %s, %s, %s)""",
                    (conv_id, final_text, body.mode, json.dumps(sources)),
                )
        except Exception as e:
            logger.error("Failed to store assistant message: %s", e)

    return StreamingResponse(event_stream(), media_type="text/event-stream")

