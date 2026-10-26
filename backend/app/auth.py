"""JWT authentication and password hashing module.

Provides:
- Secure password hashing (PBKDF2-HMAC-SHA256 with random salt)
- JWT token generation and validation
- FastAPI Dependency get_current_user_id (with demo fallback when unauthenticated)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

logger = logging.getLogger(__name__)

DEMO_USER_ID = "00000000-0000-0000-0000-000000000001"
security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Password hashing (PBKDF2-HMAC-SHA256)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 100,000 iterations and salt."""
    salt = os.urandom(16)
    kdf = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"{salt.hex()}:{kdf.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against salt:kdf string."""
    try:
        salt_hex, key_hex = hashed.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        actual_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return hmac.compare_digest(actual_key, expected_key)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT encoding & decoding (cryptographically signed HMAC-SHA256)
# ---------------------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = "=" * (4 - (len(s) % 4)) if len(s) % 4 else ""
    return base64.urlsafe_b64decode((s + padding).encode("ascii"))


def create_access_token(user_id: str, email: str, expires_minutes: int | None = None) -> str:
    """Create a signed JWT access token."""
    exp_minutes = expires_minutes or settings.jwt_expires_minutes
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + (exp_minutes * 60),
    }

    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    signing_input = f"{_b64url_encode(header_bytes)}.{_b64url_encode(payload_bytes)}"
    signature = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()

    return f"{signing_input}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate and decode a JWT access token, checking HMAC signature and expiration."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Malformed token format")

        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(
            settings.jwt_secret.encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()

        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(actual_sig, expected_sig):
            raise ValueError("Invalid signature")

        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        if payload.get("exp", 0) < int(time.time()):
            raise ValueError("Token has expired")

        return payload
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid or expired credentials: {str(exc)}")


# ---------------------------------------------------------------------------
# FastAPI Dependency
# ---------------------------------------------------------------------------

def get_current_user_id(credentials: HTTPAuthorizationCredentials | None = Security(security)) -> str:
    """Extract authenticated user ID from Authorization Bearer token.

    If no Bearer header is passed, defaults to DEMO_USER_ID for MVP / demo mode.
    If an invalid Bearer header is passed, raises HTTP 401 Unauthorized.
    """
    if credentials is None:
        # Fall back to demo user when no auth token provided
        return DEMO_USER_ID

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token payload missing subject identifier")
    return str(user_id)
