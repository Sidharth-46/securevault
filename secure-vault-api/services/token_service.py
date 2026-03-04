"""
services/token_service.py - JWT and reset-token utilities.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt

from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRY_HOURS


# ── JWT helpers ──────────────────────────────────────────────────────────────

def create_jwt(user_id: str, email: str) -> str:
    """Create a signed JWT containing the user's id and email."""
    payload = {
        "sub": user_id,
        "email": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict | None:
    """Decode and validate a JWT.  Returns the payload dict or None."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        return None


# ── Password-reset tokens ───────────────────────────────────────────────────

def generate_reset_token() -> str:
    """Return a URL-safe random token (64 chars)."""
    return secrets.token_urlsafe(48)


def generate_otp() -> str:
    """Return a random 6-digit OTP string."""
    return f"{secrets.randbelow(1_000_000):06}"
