-- AI Personal Tutor - Database Schema
-- PostgreSQL 16 + pgvector

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- Users
-- ============================================================
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT UNIQUE NOT NULL,
    password_hash TEXT,                          -- NULL for demo user; filled by JWT auth (M9)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Subjects
-- ============================================================
CREATE TABLE subjects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, name)
);

-- ============================================================
-- Documents
-- ============================================================
CREATE TABLE documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id  UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    filename    TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    mime_type   TEXT,
    file_size   BIGINT,
    status      TEXT NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'processing', 'ready', 'failed')),
    error       TEXT,
    page_count  INT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX documents_user_subject_idx ON documents (user_id, subject_id);

-- ============================================================
-- Chunks (vector + full-text search)
-- ============================================================
CREATE TABLE chunks (
    id           BIGSERIAL PRIMARY KEY,
    document_id  UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL,
    subject_id   UUID NOT NULL,
    chunk_index  INT NOT NULL,
    page_start   INT,
    page_end     INT,
    section_path TEXT,
    content      TEXT NOT NULL,
    embedding    vector(384),
    tsv          tsvector GENERATED ALWAYS AS
                 (to_tsvector('english', coalesce(section_path, '') || ' ' || content)) STORED
);

CREATE INDEX chunks_user_subject_idx ON chunks (user_id, subject_id);
CREATE INDEX chunks_document_idx ON chunks (document_id);
CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);

-- ============================================================
-- Conversations
-- ============================================================
CREATE TABLE conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id  UUID REFERENCES subjects(id) ON DELETE SET NULL,
    title       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Messages
-- ============================================================
CREATE TABLE messages (
    id               BIGSERIAL PRIMARY KEY,
    conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role             TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content          TEXT NOT NULL,
    mode             TEXT,
    sources          JSONB,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX messages_conversation_idx ON messages (conversation_id);

-- ============================================================
-- Demo user (replaced by real auth in M9)
-- ============================================================
INSERT INTO users (id, email) VALUES
    ('00000000-0000-0000-0000-000000000001', 'demo@student.dev');
