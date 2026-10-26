import sys
from unittest.mock import MagicMock, patch
import pytest

from app.rag.rewrite import rewrite_query


def test_empty_history_returns_original_question():
    question = "What is Newton's second law?"
    result = rewrite_query(question, history=[])
    assert result == question

    result_none = rewrite_query(question, history=None)
    assert result_none == question


@patch("app.rag.rewrite.settings")
def test_missing_api_key_returns_original_question(mock_settings):
    mock_settings.anthropic_api_key = ""
    history = [
        {"role": "user", "content": "What is Newton's second law?"},
        {"role": "assistant", "content": "Newton's second law states F = ma."},
    ]
    result = rewrite_query("Why does it depend on mass?", history)
    assert result == "Why does it depend on mass?"


@patch("app.rag.rewrite.settings")
def test_successful_pronoun_resolution(mock_settings):
    mock_settings.anthropic_api_key = "sk-ant-test-key-12345"
    mock_settings.rewrite_model = "claude-haiku-4-20250414"

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text="Why does Newton's second law acceleration depend on mass?")
    ]
    mock_client.messages.create.return_value = mock_response

    mock_anthropic_module = MagicMock()
    mock_anthropic_module.Anthropic.return_value = mock_client

    with patch.dict(sys.modules, {"anthropic": mock_anthropic_module}):
        history = [
            {"role": "user", "content": "What is Newton's second law?"},
            {"role": "assistant", "content": "Newton's second law states that acceleration is proportional to net force and inversely proportional to mass (F = ma)."},
        ]
        question = "Why does it depend on mass?"

        rewritten = rewrite_query(question, history)

        # Verify LLM was called with context transcript
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-20250414"
        assert "Newton's second law" in call_kwargs["messages"][0]["content"]

        # Verify rewritten query resolved pronoun
        assert rewritten == "Why does Newton's second law acceleration depend on mass?"


@patch("app.rag.rewrite.settings")
def test_api_error_falls_back_gracefully(mock_settings):
    mock_settings.anthropic_api_key = "sk-ant-test-key-12345"

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = RuntimeError("Anthropic API rate limit or network error")

    mock_anthropic_module = MagicMock()
    mock_anthropic_module.Anthropic.return_value = mock_client

    with patch.dict(sys.modules, {"anthropic": mock_anthropic_module}):
        history = [
            {"role": "user", "content": "Explain Kepler's laws."},
            {"role": "assistant", "content": "Kepler formulated three laws of planetary motion."},
        ]
        question = "What about the third one?"

        # Should not raise exception, falls back to original question
        result = rewrite_query(question, history)
        assert result == question
