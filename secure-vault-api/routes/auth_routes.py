"""
routes/auth_routes.py - Registration, login, and Google OAuth endpoints.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import bcrypt
import requests as _requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from firestore_client import db
from services.token_service import create_jwt
from config import GOOGLE_USERINFO_URL

logger = logging.getLogger("securevault.auth")
router = APIRouter()

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


# ── Request / response models ───────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleLoginRequest(BaseModel):
    access_token: str


class AuthResponse(BaseModel):
    success: bool
    message: str
    token: str | None = None
    email: str | None = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _get_user_by_email(email: str) -> tuple[str | None, dict | None]:
    """Return ``(doc_id, user_dict)`` or ``(None, None)``."""
    docs = (
        db.collection("users")
        .where("email", "==", email)
        .limit(1)
        .stream()
    )
    for doc in docs:
        return doc.id, doc.to_dict()
    return None, None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse)
def register(body: RegisterRequest):
    email = body.email.strip().lower()
    if not _EMAIL_RE.match(email):
        return AuthResponse(success=False, message="Invalid email format.")

    if len(body.password) < 6:
        return AuthResponse(
            success=False, message="Password must be at least 6 characters."
        )

    uid, _ = _get_user_by_email(email)
    if uid is not None:
        return AuthResponse(
            success=False, message="An account with this email already exists."
        )

    pw_hash = _hash_password(body.password)
    doc_ref = db.collection("users").document()
    doc_ref.set(
        {
            "email": email,
            "password_hash": pw_hash,
            "google_id": None,
            "master_pin_hash": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    token = create_jwt(doc_ref.id, email)
    logger.info("Account registered: %s", email)
    return AuthResponse(
        success=True,
        message="Account created successfully.",
        token=token,
        email=email,
    )


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest):
    email = body.email.strip().lower()
    uid, user = _get_user_by_email(email)

    if user is None:
        return AuthResponse(success=False, message="No account found with this email.")

    if not user.get("password_hash"):
        return AuthResponse(
            success=False,
            message="This account uses Google sign-in. Please use Google to log in.",
        )

    if not _verify_password(body.password, user["password_hash"]):
        logger.warning("Failed login attempt: %s", email)
        return AuthResponse(success=False, message="Incorrect password.")

    token = create_jwt(uid, email)
    logger.info("Login successful: %s", email)
    return AuthResponse(
        success=True, message="Login successful.", token=token, email=email
    )


@router.post("/google-login", response_model=AuthResponse)
def google_login(body: GoogleLoginRequest):
    """Verify a Google access token and create / retrieve the account."""
    try:
        resp = _requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {body.access_token}"},
            timeout=10,
        )
        resp.raise_for_status()
        info = resp.json()
    except Exception as exc:
        return AuthResponse(
            success=False, message=f"Google token verification failed: {exc}"
        )

    email = info.get("email", "").strip().lower()
    google_id = info.get("sub", "")
    if not email:
        return AuthResponse(
            success=False, message="Could not retrieve email from Google."
        )

    uid, user = _get_user_by_email(email)

    if user is None:
        # Create new user
        doc_ref = db.collection("users").document()
        doc_ref.set(
            {
                "email": email,
                "password_hash": None,
                "google_id": google_id,
                "master_pin_hash": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        uid = doc_ref.id
    else:
        # Link google_id if missing
        if not user.get("google_id"):
            db.collection("users").document(uid).update({"google_id": google_id})

    token = create_jwt(uid, email)
    logger.info("Google login successful: %s", email)
    return AuthResponse(
        success=True, message="Google login successful.", token=token, email=email
    )
