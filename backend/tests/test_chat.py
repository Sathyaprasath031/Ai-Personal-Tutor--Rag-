"""Unit and integration tests for chat and streaming answer generation."""

import json
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.rag.prompts import build_system_prompt, BASE_PROMPT, MODES
from app.rag.answer import format_sources_xml, format_sse, answer_stream
from app.main import app


def test_build_system_prompt_grounding_and_modes():
    # Test explain mode
    prompt_explain = build_system_prompt("explain")
    assert "GROUNDING & INTEGRITY RULES" in prompt_explain
    assert "cite them inline like [S1], [S2]" in prompt_explain or "[S1], [S2]" in prompt_explain
    assert "TEACHING MODE: Standard Explanation" in prompt_explain

    # Test quiz mode
    prompt_quiz = build_system_prompt("quiz")
    assert "TEACHING MODE: Interactive Quiz" in prompt_quiz
    assert "Do NOT reveal the answers yet" in prompt_quiz

    # Test socratic mode
    prompt_socratic = build_system_prompt("socratic")
    assert "TEACHING MODE: Socratic Method" in prompt_socratic
    assert "Do NOT reveal the full answer directly" in prompt_socratic


def test_format_sources_xml():
    chunks = [
        {
            "filename": "physics.pdf",
            "page_start": 1,
            "page_end": 2,
            "section": "Kinematics",
            "content": "Velocity is displacement over time.",
        },
        {
            "filename": "physics.pdf",
            "page_start": 5,
            "page_end": 5,
            "section": "Dynamics",
            "content": "Force equals mass times acceleration.",
        },
    ]
    xml = format_sources_xml(chunks)

    assert "<sources>" in xml
    assert "</sources>" in xml
    assert '<source id="S1" file="physics.pdf" pages="pp.1-2" section="Kinematics">' in xml
    assert "Velocity is displacement over time." in xml
    assert '<source id="S2" file="physics.pdf" pages="p.5" section="Dynamics">' in xml
    assert "Force equals mass times acceleration." in xml


def test_format_sse():
    sse_token = format_sse("token", "Hello")
    assert sse_token == 'event: token\ndata: "Hello"\n\n'

    sse_sources = format_sse("sources", [{"id": "S1"}])
    assert sse_sources == 'event: sources\ndata: [{"id": "S1"}]\n\n'


@patch("app.rag.answer.hybrid_search")
@patch("app.rag.answer.rerank")
@patch("app.rag.answer.rewrite_query")
def test_answer_stream_generation(mock_rewrite, mock_rerank, mock_search):
    mock_rewrite.return_value = "Explain Newton's second law"
    mock_search.return_value = [
        {
            "chunk_id": 1,
            "document_id": "doc-1",
            "filename": "physics.pdf",
            "page_start": 1,
            "page_end": 1,
            "section": "Newton's Laws",
            "content": "F = ma relates force, mass, and acceleration.",
            "rrf_score": 0.03,
        }
    ]
    mock_rerank.return_value = [
        {
            "chunk_id": 1,
            "document_id": "doc-1",
            "filename": "physics.pdf",
            "page_start": 1,
            "page_end": 1,
            "section": "Newton's Laws",
            "content": "F = ma relates force, mass, and acceleration.",
            "score": 0.95,
        }
    ]

    events = list(answer_stream(
        user_id="00000000-0000-0000-0000-000000000001",
        question="What is Newton's second law?",
        history=[],
    ))

    # Should contain token events, a sources event, and a done event
    has_token = any(e.startswith("event: token") for e in events)
    has_sources = any(e.startswith("event: sources") for e in events)
    has_done = any(e.startswith("event: done") for e in events)

    assert has_token
    assert has_sources
    assert has_done


@patch("app.main.pool")
@patch("app.main.answer_stream")
def test_chat_api_endpoint(mock_answer_stream, mock_pool):
    # Mock DB connection
    mock_conn = MagicMock()
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = ("conv-uuid-123",)
    mock_conn.execute.return_value.fetchall.return_value = []

    # Mock answer_stream generator
    mock_answer_stream.return_value = [
        'event: token\ndata: "F = ma"\n\n',
        'event: sources\ndata: [{"id": "S1", "filename": "physics.pdf"}]\n\n',
        'event: done\ndata: {"text": "F = ma"}\n\n',
    ]

    client = TestClient(app)
    response = client.post("/chat", json={
        "question": "What is F = ma?",
        "mode": "explain",
    })

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    content = response.text
    assert "event: meta" in content
    assert "conv-uuid-123" in content
    assert "event: token" in content
    assert "F = ma" in content
    assert "event: sources" in content
    assert "event: done" in content
