"""Ingestion pipeline job — called by the RQ worker.

Flow: parse → chunk → embed → store in PostgreSQL.
Updates documents.status throughout.
"""

from __future__ import annotations

import logging
import traceback

from ..db import pool
from .chunker import chunk_document
from .embedder import embed_passages
from .parser import parse_file

logger = logging.getLogger(__name__)


def _set_status(doc_id: str, status: str, *,
                error: str | None = None, page_count: int | None = None):
    """Update the document's status in the database."""
    with pool.connection() as conn:
        conn.execute(
            """UPDATE documents
               SET status = %s,
                   error = %s,
                   page_count = COALESCE(%s, page_count)
               WHERE id = %s""",
            (status, error, page_count, doc_id),
        )


def _get_document(doc_id: str) -> tuple[str, str, str]:
    """Fetch document metadata. Returns (user_id, subject_id, file_path)."""
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT user_id, subject_id, file_path FROM documents WHERE id = %s",
            (doc_id,),
        ).fetchone()
    if not row:
        raise ValueError(f"Document {doc_id} not found in database")
    return str(row[0]), str(row[1]), row[2]


def ingest_document(doc_id: str) -> None:
    """RQ job: parse → chunk → embed → store.

    Called as: queue.enqueue("app.ingestion.pipeline.ingest_document", doc_id)
    """
    logger.info("Starting ingestion for document %s", doc_id)

    try:
        _set_status(doc_id, "processing")

        # 1. Fetch document metadata
        user_id, subject_id, file_path = _get_document(doc_id)
        logger.info("Parsing file: %s", file_path)

        # 2. Parse
        parsed = parse_file(file_path)
        logger.info("Parsed %d blocks across %d pages", len(parsed.blocks), parsed.page_count)

        # 3. Chunk
        chunks = chunk_document(parsed)
        if not chunks:
            raise ValueError("No extractable text found in this file.")
        logger.info("Created %d chunks", len(chunks))

        # 4. Embed (contextual: section_path + content)
        texts_to_embed = [
            f"{chunk.section_path}\n{chunk.content}" for chunk in chunks
        ]
        logger.info("Embedding %d chunks...", len(chunks))
        vectors = embed_passages(texts_to_embed)
        logger.info("Embedding complete")

        # 5. Store chunks in database
        with pool.connection() as conn:
            # Clear any previous chunks for this document (re-ingestion)
            conn.execute("DELETE FROM chunks WHERE document_id = %s", (doc_id,))

            # Batch insert
            with conn.cursor() as cur:
                for chunk, vector in zip(chunks, vectors):
                    cur.execute(
                        """INSERT INTO chunks
                           (document_id, user_id, subject_id, chunk_index,
                            page_start, page_end, section_path, content, embedding)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector)""",
                        (
                            doc_id, user_id, subject_id, chunk.index,
                            chunk.page_start, chunk.page_end,
                            chunk.section_path, chunk.content, vector,
                        ),
                    )
            logger.info("Stored %d chunks in database", len(chunks))

        # 6. Mark as ready
        _set_status(doc_id, "ready", page_count=parsed.page_count)
        logger.info("Document %s ingestion complete — status=ready", doc_id)

    except Exception as exc:
        logger.error("Ingestion failed for document %s: %s", doc_id, exc)
        traceback.print_exc()
        _set_status(doc_id, "failed", error=str(exc)[:500])
        raise
