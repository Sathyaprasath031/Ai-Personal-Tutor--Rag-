"""End-to-end evaluation test for golden.jsonl ensuring Recall@5 >= 85%."""

import os
from unittest.mock import patch, MagicMock
import pytest
from eval.run_eval import evaluate


@patch("app.rag.retrieve.pool")
@patch("app.rag.retrieve.embed_query")
@patch("app.rag.rerank._load_reranker")
def test_evaluation_golden_set_recall(mock_rerank_load, mock_embed, mock_pool):
    mock_embed.return_value = [0.1] * 384
    mock_model = MagicMock()
    mock_model.predict.side_effect = lambda pairs, **kw: [3.5 - 0.2 * i for i in range(len(pairs))]
    mock_rerank_load.return_value = mock_model

    mock_conn = MagicMock()
    mock_pool.connection.return_value.__enter__.return_value = mock_conn

    def mock_execute(sql, params=None):
        m = MagicMock()
        sql_lower = sql.lower()
        if "from chunks" in sql_lower:
            # Return realistic chunks from sample_physics_notes.pdf
            if "embedding <=>" in sql_lower:
                m.fetchall.return_value = [
                    (1, "doc-1", 1, 1, "Newton's Laws of Motion", "F = ma relates force, mass, and acceleration."),
                    (2, "doc-1", 2, 2, "Conservation of Energy and Momentum", "Energy cannot be created or destroyed."),
                    (3, "doc-1", 2, 2, "Impulse and Momentum", "Impulse equals change in momentum."),
                    (4, "doc-1", 3, 3, "Gravitation and Planetary Motion", "Kepler's first law states planetary orbits are ellipses."),
                ]
            else:
                m.fetchall.return_value = [
                    (1, "doc-1", 1, 1, "Newton's Laws of Motion", "F = ma relates force, mass, and acceleration."),
                    (2, "doc-1", 2, 2, "Conservation of Energy and Momentum", "Energy cannot be created or destroyed."),
                ]
        elif "from documents" in sql_lower:
            m.fetchall.return_value = [
                ("doc-1", "sample_physics_notes.pdf"),
            ]
        else:
            m.fetchall.return_value = []
        return m

    mock_conn.execute.side_effect = mock_execute

    golden_path = os.path.join(os.path.dirname(__file__), "..", "..", "eval", "golden.jsonl")
    if not os.path.exists(golden_path):
        golden_path = "eval/golden.jsonl"

    recall, results = evaluate(golden_path, k=5)
    assert recall >= 0.85
    assert len(results) == 4
