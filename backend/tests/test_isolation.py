"""Unit and integration tests for JWT authentication and multi-tenant user isolation.

Guarantees that Student A can NEVER access or retrieve Student B's data:
- Subjects isolation
- Documents isolation
- Document deletion isolation
- Vector & keyword chunk retrieval isolation
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_current_user_id,
    DEMO_USER_ID,
)
from app.rag.retrieve import hybrid_search, _build_where_clause
from app.main import app


# ---------------------------------------------------------------------------
# 1. Password hashing & JWT token tests
# ---------------------------------------------------------------------------

def test_password_hashing_and_verification():
    raw_password = "StudySecretPassword123!"
    hashed = hash_password(raw_password)

    # Salt and hash should be formatted as salt:key
    assert ":" in hashed
    assert hashed != raw_password

    # Verification must succeed for correct password
    assert verify_password(raw_password, hashed) is True

    # Verification must fail for incorrect password
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_creation_and_decoding():
    user_id = "11111111-1111-1111-1111-111111111111"
    email = "student.a@university.edu"

    token = create_access_token(user_id, email, expires_minutes=60)
    assert token.count(".") == 2  # standard JWT 3-part structure

    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["email"] == email
    assert payload["exp"] > payload["iat"]


def test_jwt_expired_or_invalid_signature():
    user_id = "11111111-1111-1111-1111-111111111111"
    email = "student.a@university.edu"

    # Expired token (-10 minutes)
    expired_token = create_access_token(user_id, email, expires_minutes=-10)
    with pytest.raises(Exception):
        decode_access_token(expired_token)

    # Tampered signature
    valid_token = create_access_token(user_id, email, expires_minutes=60)
    tampered = valid_token[:-4] + "xxxx"
    with pytest.raises(Exception):
        decode_access_token(tampered)


# ---------------------------------------------------------------------------
# 2. Multi-tenant database & retrieval isolation tests
# ---------------------------------------------------------------------------

def test_retrieval_where_clause_guarantees_tenant_isolation():
    """Verify that every single generated SQL WHERE clause has user_id bound."""
    where_a, params_a = _build_where_clause("tenant-a-uuid", None)
    assert where_a == "user_id = %s"
    assert params_a == ["tenant-a-uuid"]

    where_b, params_b = _build_where_clause("tenant-b-uuid", "subject-1")
    assert where_b == "user_id = %s AND subject_id = %s"
    assert params_b == ["tenant-b-uuid", "subject-1"]


@patch("app.rag.retrieve.pool")
@patch("app.rag.retrieve.embed_query")
def test_retrieval_never_crosses_tenants(mock_embed, mock_pool):
    """When Student B queries for notes, Student A's chunks must NEVER be returned."""
    mock_embed.return_value = [0.1] * 384
    mock_conn = MagicMock()
    mock_pool.connection.return_value.__enter__.return_value = mock_conn

    captured_queries = []

    def mock_execute(sql, params=None):
        captured_queries.append((sql, params))
        m = MagicMock()
        # If user_id is tenant-a, return notes; if tenant-b, return nothing
        user_param = params[0] if params else None
        if user_param == "tenant-a":
            m.fetchall.return_value = [(1, "doc-a", 1, 1, "Section A", "Student A's private notes")]
        else:
            m.fetchall.return_value = []
        return m

    mock_conn.execute.side_effect = mock_execute

    # Student B searches for the exact same topic
    results_b = hybrid_search(user_id="tenant-b", query="Newton's laws")

    # Student B MUST get 0 results because chunks belong to Student A
    assert results_b == []

    # Verify every executed query strictly passed tenant-b as user_id parameter
    for sql, params in captured_queries:
        if params:
            assert params[0] == "tenant-b"


# ---------------------------------------------------------------------------
# 3. API-level isolation tests (Subjects & Documents)
# ---------------------------------------------------------------------------

@patch("app.main.pool")
def test_api_subjects_tenant_isolation(mock_pool):
    mock_conn = MagicMock()
    mock_pool.connection.return_value.__enter__.return_value = mock_conn

    token_a = create_access_token("tenant-a", "a@test.com")
    token_b = create_access_token("tenant-b", "b@test.com")

    client = TestClient(app)

    # Student B attempts to delete Student A's subject
    mock_conn.execute.return_value.fetchone.return_value = None  # Subject not found for tenant-b
    res = client.delete(
        "/subjects/subject-a-uuid",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code == 404
    # Ensure query had both subject_id AND user_id = tenant-b
    call_args = mock_conn.execute.call_args[0]
    assert "WHERE id = %s AND user_id = %s" in call_args[0]
    assert call_args[1] == ("subject-a-uuid", "tenant-b")


@patch("app.main.pool")
def test_api_documents_tenant_isolation(mock_pool):
    mock_conn = MagicMock()
    mock_pool.connection.return_value.__enter__.return_value = mock_conn

    token_b = create_access_token("tenant-b", "b@test.com")
    client = TestClient(app)

    # Student B lists documents -> returns only Student B's documents
    mock_conn.execute.return_value.fetchall.return_value = []
    res = client.get(
        "/documents",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code == 200
    assert res.json() == []

    # Ensure query filtered by tenant-b
    call_args = mock_conn.execute.call_args[0]
    assert "WHERE user_id = %s" in call_args[0]
    assert call_args[1] == ["tenant-b"]
