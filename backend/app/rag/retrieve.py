"""Hybrid retrieval combining dense vector search (pgvector) and sparse FTS (tsvector).

Uses Reciprocal Rank Fusion (RRF, k=60) to merge rankings.
Always strictly filters by user_id to enforce multi-tenant isolation.
"""

from __future__ import annotations

import logging
from typing import Any

from ..db import pool
from ..ingestion.embedder import embed_query

logger = logging.getLogger(__name__)


def _build_where_clause(user_id: str, subject_id: str | None) -> tuple[str, list[Any]]:
    """Build parameterized WHERE clause ensuring user isolation."""
    where = "user_id = %s"
    params: list[Any] = [user_id]
    if subject_id:
        where += " AND subject_id = %s"
        params.append(subject_id)
    return where, params


def dense_search(
    user_id: str,
    query: str,
    subject_id: str | None = None,
    limit: int = 30,
) -> list[tuple]:
    """Execute dense vector similarity search using pgvector cosine distance."""
    qvec = embed_query(query)
    where, params = _build_where_clause(user_id, subject_id)
    cols = "id, document_id, page_start, page_end, section_path, content"

    sql = f"""
        SELECT {cols}
        FROM chunks
        WHERE {where}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    with pool.connection() as conn:
        rows = conn.execute(sql, params + [qvec, limit]).fetchall()
    return rows


def sparse_search(
    user_id: str,
    query: str,
    subject_id: str | None = None,
    limit: int = 30,
) -> list[tuple]:
    """Execute sparse keyword full-text search using PostgreSQL tsvector."""
    where, params = _build_where_clause(user_id, subject_id)
    cols = "id, document_id, page_start, page_end, section_path, content"

    # Use websearch_to_tsquery for safe query parsing (handles spaces, quotes, operators)
    sql = f"""
        SELECT {cols}
        FROM chunks
        WHERE {where} AND tsv @@ websearch_to_tsquery('english', %s)
        ORDER BY ts_rank_cd(tsv, websearch_to_tsquery('english', %s)) DESC
        LIMIT %s
    """
    try:
        with pool.connection() as conn:
            rows = conn.execute(sql, params + [query, query, limit]).fetchall()
        return rows
    except Exception as exc:
        logger.warning("FTS search encountered an issue with query '%s': %s", query, exc)
        return []


def hybrid_search(
    user_id: str,
    query: str,
    subject_id: str | None = None,
    k_each: int = 30,
    k_final: int = 20,
) -> list[dict]:
    """Perform hybrid retrieval (dense + sparse) merged with Reciprocal Rank Fusion."""
    dense_results = dense_search(user_id, query, subject_id, limit=k_each)
    sparse_results = sparse_search(user_id, query, subject_id, limit=k_each)

    # Fetch document filenames for the user
    with pool.connection() as conn:
        doc_rows = conn.execute(
            "SELECT id::text, filename FROM documents WHERE user_id = %s",
            (user_id,),
        ).fetchall()
        filenames = {str(row[0]): row[1] for row in doc_rows}

    # Reciprocal Rank Fusion (RRF, constant K = 60)
    K = 60
    rrf_scores: dict[int, float] = {}
    chunk_data: dict[int, tuple] = {}

    for result_set in (dense_results, sparse_results):
        for rank, row in enumerate(result_set):
            chunk_id = row[0]
            score = 1.0 / (K + rank + 1)
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + score
            if chunk_id not in chunk_data:
                chunk_data[chunk_id] = row

    # Sort by fused score descending
    sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)[:k_final]

    candidates = []
    for cid in sorted_ids:
        row = chunk_data[cid]
        doc_id_str = str(row[1])
        candidates.append({
            "chunk_id": row[0],
            "document_id": doc_id_str,
            "filename": filenames.get(doc_id_str, "Document"),
            "page_start": row[2] or 1,
            "page_end": row[3] or 1,
            "section": row[4] or "General",
            "content": row[5],
            "rrf_score": rrf_scores[cid],
        })

    logger.info("Hybrid search found %d dense, %d sparse -> %d fused candidates",
                len(dense_results), len(sparse_results), len(candidates))
    return candidates
