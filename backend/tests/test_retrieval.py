"""Unit and integration tests for hybrid search, RRF fusion, reranker, and relevance gate."""

from unittest.mock import MagicMock, patch
import pytest

from app.rag.retrieve import hybrid_search, _build_where_clause
from app.rag.rerank import rerank
from app.rag.prompts import NOT_FOUND_HINT
from app.rag.answer import answer_stream
from app.config import settings


def test_where_clause_enforces_user_isolation():
    where_user, params_user = _build_where_clause("user-1", None)
    assert where_user == "user_id = %s"
    assert params_user == ["user-1"]

    where_sub, params_sub = _build_where_clause("user-1", "subject-42")
    assert where_sub == "user_id = %s AND subject_id = %s"
    assert params_sub == ["user-1", "subject-42"]


@patch("app.rag.retrieve.pool")
@patch("app.rag.retrieve.embed_query")
def test_hybrid_search_rrf_fusion(mock_embed, mock_pool):
    mock_embed.return_value = [0.1] * 384
    mock_conn = MagicMock()
    mock_pool.connection.return_value.__enter__.return_value = mock_conn

    # Dense results: chunk 1 (rank 0), chunk 2 (rank 1)
    dense_rows = [
        (1, "doc-1", 1, 1, "Newton", "First law of motion"),
        (2, "doc-1", 2, 2, "Energy", "Conservation of energy"),
    ]
    # Sparse results: chunk 2 (rank 0 - keyword match), chunk 3 (rank 1)
    sparse_rows = [
        (2, "doc-1", 2, 2, "Energy", "Conservation of energy"),
        (3, "doc-1", 3, 3, "Gravity", "Orbital mechanics"),
    ]
    # Document filenames
    doc_rows = [("doc-1", "physics.pdf")]

    mock_conn.execute.side_effect = [
        MagicMock(fetchall=lambda: dense_rows),   # dense_search
        MagicMock(fetchall=lambda: sparse_rows),  # sparse_search
        MagicMock(fetchall=lambda: doc_rows),     # filenames
    ]

    candidates = hybrid_search("user-1", "Conservation of energy", k_final=10)

    # Chunk 2 appeared in BOTH dense and sparse -> highest RRF score
    assert len(candidates) == 3
    assert candidates[0]["chunk_id"] == 2
    assert candidates[0]["filename"] == "physics.pdf"
    assert candidates[0]["rrf_score"] > candidates[1]["rrf_score"]


def test_reranker_scoring_and_ranking():
    candidates = [
        {"chunk_id": 1, "section": "Newton", "content": "An object at rest stays at rest.", "rrf_score": 0.03},
        {"chunk_id": 2, "section": "Energy", "content": "Energy is conserved in isolated systems.", "rrf_score": 0.02},
    ]

    with patch("app.rag.rerank._load_reranker") as mock_load:
        mock_model = MagicMock()
        # Mock raw logits: candidate 1 is very relevant (logit +4.0), candidate 2 is irrelevant (logit -4.0)
        mock_model.predict.return_value = [4.0, -4.0]
        mock_load.return_value = mock_model

        ranked = rerank("What is Newton's first law of motion?", candidates, top_n=2)

        assert len(ranked) == 2
        assert ranked[0]["chunk_id"] == 1
        # Sigmoid(4.0) is ~0.982
        assert ranked[0]["score"] > 0.95
        # Sigmoid(-4.0) is ~0.018
        assert ranked[1]["score"] < 0.05


@patch("app.rag.answer.hybrid_search")
@patch("app.rag.answer.rerank")
@patch("app.rag.answer.rewrite_query")
def test_relevance_gate_filters_irrelevant_queries(mock_rewrite, mock_rerank, mock_search):
    """When questions are outside notes, rerank scores fall below threshold and trigger NOT_FOUND_HINT."""
    mock_rewrite.return_value = "What is the capital of Australia?"
    mock_search.return_value = [
        {
            "chunk_id": 1,
            "filename": "physics.pdf",
            "page_start": 1,
            "page_end": 1,
            "section": "Newton",
            "content": "F = ma",
            "rrf_score": 0.01,
        }
    ]
    # Reranker scores F=ma as completely irrelevant to capital of Australia
    # score (0.02) is well below settings.relevance_threshold (0.15)
    mock_rerank.return_value = [
        {
            "chunk_id": 1,
            "filename": "physics.pdf",
            "page_start": 1,
            "page_end": 1,
            "section": "Newton",
            "content": "F = ma",
            "score": 0.02,
        }
    ]

    events = list(answer_stream(
        user_id="user-1",
        question="What is the capital of Australia?",
    ))

    # Sources event should be empty because relevance gate filtered out the chunk
    sources_event = next(e for e in events if e.startswith("event: sources"))
    import json
    sources_data = json.loads(sources_event.split("data: ", 1)[1])
    assert sources_data == []
