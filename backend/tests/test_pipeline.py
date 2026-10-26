"""Unit and mock tests for the ingestion pipeline."""

from unittest.mock import MagicMock, patch
import pytest

from app.ingestion.parser import ParsedDoc, Block
from app.ingestion.chunker import Chunk
from app.ingestion.pipeline import ingest_document


@patch("app.ingestion.pipeline.parse_file")
@patch("app.ingestion.pipeline.chunk_document")
@patch("app.ingestion.pipeline.embed_passages")
@patch("app.ingestion.pipeline.pool")
def test_ingest_document_success(mock_pool, mock_embed, mock_chunk, mock_parse):
    # Mock database connection and queries
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_pool.connection.return_value.__enter__.return_value = mock_conn

    # SELECT user_id, subject_id, file_path
    mock_conn.execute.return_value.fetchone.return_value = (
        "00000000-0000-0000-0000-000000000001",
        "sub-123",
        "/data/uploads/sample.pdf",
    )

    # Mock parser output
    mock_parse.return_value = ParsedDoc(
        blocks=[
            Block(page=1, text="Kinematics", is_heading=True),
            Block(page=1, text="Velocity is the rate of change of position with respect to time.", is_heading=False),
        ],
        page_count=1,
    )

    # Mock chunker output
    mock_chunk.return_value = [
        Chunk(
            index=0,
            page_start=1,
            page_end=1,
            section_path="Kinematics",
            content="Velocity is the rate of change of position with respect to time.",
        )
    ]

    # Mock embedder output (384-d vector)
    mock_embed.return_value = [[0.1] * 384]

    # Run ingestion
    ingest_document("doc-test-123")

    # Verify parse, chunk, embed were called
    mock_parse.assert_called_once_with("/data/uploads/sample.pdf")
    mock_chunk.assert_called_once()
    mock_embed.assert_called_once()

    # Verify status updates: 1 processing, 1 ready
    status_calls = [
        call for call in mock_conn.execute.call_args_list
        if "UPDATE documents SET status" in call[0][0] or "UPDATE documents\n               SET status" in call[0][0]
    ]
    assert len(status_calls) >= 2


@patch("app.ingestion.pipeline.parse_file")
@patch("app.ingestion.pipeline.chunk_document")
@patch("app.ingestion.pipeline.pool")
def test_ingest_document_empty_fails(mock_pool, mock_chunk, mock_parse):
    mock_conn = MagicMock()
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = (
        "00000000-0000-0000-0000-000000000001",
        "sub-123",
        "/data/uploads/empty.pdf",
    )

    mock_parse.return_value = ParsedDoc(blocks=[], page_count=1)
    mock_chunk.return_value = []  # No chunks generated

    with pytest.raises(ValueError, match="No extractable text"):
        ingest_document("doc-empty-123")

    # Verify status was updated to failed
    status_calls = [
        call for call in mock_conn.execute.call_args_list
        if "failed" in str(call)
    ]
    assert len(status_calls) >= 1
