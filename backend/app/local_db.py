"""Local embedded SQLite + NumPy vector database adapter.

Provides seamless local execution when PostgreSQL/Docker is not running.
Stores data in data/tutor_local.db and computes cosine similarity with NumPy.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

def _find_db_path() -> Path:
    this_dir = Path(__file__).resolve().parent
    candidates = [
        this_dir.parent / "data" / "tutor_local.db",
        this_dir.parent.parent / "data" / "tutor_local.db",
        Path("data") / "tutor_local.db",
        Path("backend/data") / "tutor_local.db",
    ]
    for c in candidates:
        if c.exists():
            return c
    target = candidates[0]
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


DB_PATH = _find_db_path()


class TimestampStr(str):
    """String subclass that provides an .isoformat() method for compatibility with psycopg timestamps."""
    def isoformat(self) -> str:
        return str(self)


def _wrap_value(val: Any) -> Any:
    if isinstance(val, str) and len(val) >= 10 and ("-" in val or ":" in val):
        # Possible timestamp string like '2026-10-21 08:30:00' or ISO string
        return TimestampStr(val)
    return val


def _wrap_row(row: tuple | sqlite3.Row) -> tuple:
    return tuple(_wrap_value(item) for item in row)


class LocalCursor:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cursor = conn.cursor()
        self._last_rows: list[tuple] = []
        self._pos = 0

    @property
    def rowcount(self) -> int:
        return self.cursor.rowcount

    @property
    def description(self):
        return self.cursor.description

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cursor.close()

    def execute(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> LocalCursor:
        params = list(params) if params else []
        clean_sql = sql.strip()

        # Handle Vector Cosine Distance Search: ORDER BY embedding <=> %s::vector LIMIT %s
        if "embedding <=>" in clean_sql:
            self._execute_vector_search(clean_sql, params)
            return self

        # Handle Sparse FTS Search: tsv @@ websearch_to_tsquery('english', %s)
        if "websearch_to_tsquery" in clean_sql:
            self._execute_keyword_search(clean_sql, params)
            return self

        # Handle automatic UUID generation when inserting into users, subjects, conversations
        gen_uuid = None
        if re.search(r"INSERT\s+INTO\s+users\s*\(\s*email", clean_sql, re.IGNORECASE):
            gen_uuid = str(uuid.uuid4())
            clean_sql = re.sub(r"INSERT\s+INTO\s+users\s*\(\s*email", "INSERT INTO users (id, email", clean_sql, flags=re.IGNORECASE)
            clean_sql = re.sub(r"VALUES\s*\(", "VALUES (%s, ", clean_sql, flags=re.IGNORECASE)
            params = [gen_uuid] + params
        elif re.search(r"INSERT\s+INTO\s+subjects\s*\(\s*user_id", clean_sql, re.IGNORECASE):
            gen_uuid = str(uuid.uuid4())
            clean_sql = re.sub(r"INSERT\s+INTO\s+subjects\s*\(\s*user_id", "INSERT INTO subjects (id, user_id", clean_sql, flags=re.IGNORECASE)
            clean_sql = re.sub(r"VALUES\s*\(", "VALUES (%s, ", clean_sql, flags=re.IGNORECASE)
            params = [gen_uuid] + params
        elif re.search(r"INSERT\s+INTO\s+conversations\s*\(\s*user_id", clean_sql, re.IGNORECASE):
            gen_uuid = str(uuid.uuid4())
            clean_sql = re.sub(r"INSERT\s+INTO\s+conversations\s*\(\s*user_id", "INSERT INTO conversations (id, user_id", clean_sql, flags=re.IGNORECASE)
            clean_sql = re.sub(r"VALUES\s*\(", "VALUES (%s, ", clean_sql, flags=re.IGNORECASE)
            params = [gen_uuid] + params

        # Handle RETURNING clauses (SQLite 3.35+ supports basic RETURNING, but let's emulate safely)
        returning_cols = None
        if " RETURNING " in clean_sql.upper():
            parts = re.split(r"\s+RETURNING\s+", clean_sql, flags=re.IGNORECASE)
            clean_sql = parts[0]
            returning_cols = [c.strip() for c in parts[1].split(",")]

        # Replace PostgreSQL syntax with SQLite compatible syntax
        sqlite_sql = clean_sql
        sqlite_sql = re.sub(r"%s", "?", sqlite_sql)
        sqlite_sql = re.sub(r"::vector", "", sqlite_sql)
        sqlite_sql = re.sub(r"::text", "", sqlite_sql)
        sqlite_sql = re.sub(r"ILIKE", "LIKE", sqlite_sql, flags=re.IGNORECASE)

        # Handle vector parameter in regular INSERT/UPDATE
        sanitized_params = []
        for p in params:
            if isinstance(p, (list, np.ndarray)):
                sanitized_params.append(json.dumps(list(p)))
            else:
                sanitized_params.append(p)

        self.cursor.execute(sqlite_sql, sanitized_params)

        if returning_cols:
            if self.cursor.rowcount == 0 and "DELETE" in clean_sql.upper():
                self._last_rows = []
                self._pos = 0
                self.conn.commit()
                return self

            last_id = self.cursor.lastrowid
            now_iso = TimestampStr(datetime.now(timezone.utc).isoformat())
            row = []
            for col in returning_cols:
                col_lower = col.lower()
                if col_lower == "id":
                    row.append(gen_uuid or (sanitized_params[0] if sanitized_params and isinstance(sanitized_params[0], str) and len(sanitized_params[0]) == 36 else last_id))
                elif col_lower == "name":
                    name_val = next((p for p in sanitized_params if isinstance(p, str) and len(p) < 100 and p != gen_uuid), "Default")
                    row.append(name_val)
                elif col_lower == "created_at":
                    row.append(now_iso)
                elif col_lower == "file_path":
                    row.append(sanitized_params[-1] if sanitized_params else "")
                else:
                    row.append(None)
            self._last_rows = [tuple(row)]
            self._pos = 0
            self.conn.commit()
            return self

        try:
            raw_rows = self.cursor.fetchall()
            self._last_rows = [_wrap_row(r) for r in raw_rows]
        except sqlite3.OperationalError:
            self._last_rows = []
        self._pos = 0
        self.conn.commit()
        return self

    def executemany(self, sql: str, seq_of_params: list[Any]) -> None:
        for p in seq_of_params:
            self.execute(sql, p)

    def _execute_vector_search(self, sql: str, params: list[Any]) -> None:
        """Simulate pgvector <=> cosine similarity search using NumPy."""
        limit = params[-1]
        qvec = np.array(params[-2], dtype=np.float32)

        # Filters: user_id, optional subject_id
        filter_params = params[:-2]
        user_id = filter_params[0]
        subject_id = filter_params[1] if len(filter_params) > 1 else None

        base_sql = "SELECT id, document_id, page_start, page_end, section_path, content, embedding FROM chunks WHERE user_id = ?"
        f_params = [user_id]
        if subject_id:
            base_sql += " AND subject_id = ?"
            f_params.append(subject_id)

        self.cursor.execute(base_sql, f_params)
        all_chunks = self.cursor.fetchall()

        if not all_chunks:
            self._last_rows = []
            self._pos = 0
            return

        scored_chunks = []
        qnorm = np.linalg.norm(qvec) or 1.0

        for row in all_chunks:
            cid, doc_id, p_start, p_end, sec, content, emb_json = row
            try:
                emb = np.array(json.loads(emb_json), dtype=np.float32)
                enorm = np.linalg.norm(emb) or 1.0
                cosine_sim = float(np.dot(qvec, emb) / (qnorm * enorm))
                cosine_dist = 1.0 - cosine_sim
            except Exception:
                cosine_dist = 1.0

            scored_chunks.append((cosine_dist, (cid, doc_id, p_start, p_end, sec, content)))

        scored_chunks.sort(key=lambda x: x[0])
        self._last_rows = [item[1] for item in scored_chunks[:limit]]
        self._pos = 0

    def _execute_keyword_search(self, sql: str, params: list[Any]) -> None:
        """Simulate PostgreSQL tsvector full-text search with case-insensitive word matching."""
        limit = params[-1]
        query_text = params[-2].lower()

        words = [w for w in re.findall(r"\w+", query_text) if len(w) > 2]
        filter_params = params[:-3]  # excludes query, query, limit
        user_id = filter_params[0]
        subject_id = filter_params[1] if len(filter_params) > 1 else None

        base_sql = "SELECT id, document_id, page_start, page_end, section_path, content FROM chunks WHERE user_id = ?"
        f_params = [user_id]
        if subject_id:
            base_sql += " AND subject_id = ?"
            f_params.append(subject_id)

        self.cursor.execute(base_sql, f_params)
        all_chunks = self.cursor.fetchall()

        scored = []
        for row in all_chunks:
            cid, doc_id, p_start, p_end, sec, content = row
            text_corpus = f"{sec or ''} {content}".lower()
            match_count = sum(1 for w in words if w in text_corpus)
            if match_count > 0:
                scored.append((match_count, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        self._last_rows = [item[1] for item in scored[:limit]]
        self._pos = 0

    def fetchone(self) -> tuple | None:
        if self._pos < len(self._last_rows):
            row = self._last_rows[self._pos]
            self._pos += 1
            return row
        return None

    def fetchall(self) -> list[tuple]:
        rows = self._last_rows[self._pos:]
        self._pos = len(self._last_rows)
        return rows


class LocalConnection:
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()

    def cursor(self) -> LocalCursor:
        return LocalCursor(self.conn)

    def execute(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> LocalCursor:
        cursor = LocalCursor(self.conn)
        cursor.execute(sql, params)
        return cursor

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()


class LocalDatabasePool:
    """Fallback connection pool providing a local SQLite database with vector emulation."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        with conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS subjects (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    mime_type TEXT,
                    file_size INTEGER,
                    status TEXT NOT NULL DEFAULT 'queued',
                    error TEXT,
                    page_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    page_start INTEGER,
                    page_end INTEGER,
                    section_path TEXT,
                    content TEXT NOT NULL,
                    embedding TEXT
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    subject_id TEXT,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    mode TEXT,
                    sources TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                INSERT OR IGNORE INTO users (id, email)
                VALUES ('00000000-0000-0000-0000-000000000001', 'demo@student.dev');
            """)
        conn.close()
        logger.info("Initialized local SQLite vector database at %s", self.db_path)

    @contextmanager
    def connection(self):
        local_conn = LocalConnection(self.db_path)
        try:
            yield local_conn
        finally:
            local_conn.conn.close()

    def open(self):
        self._init_db()

    def close(self):
        pass
