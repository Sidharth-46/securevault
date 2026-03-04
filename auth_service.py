"""
auth_service.py - Account authentication for Secure File Vault.

Handles:
  • Email / password registration and login (via backend API)
  • Google OAuth 2.0 (installed-application flow → backend verification)
  • In-memory session management (JWT stored in memory only)

All credential storage and verification is done server-side.
"""

from __future__ import annotations

import os
import re

import api_client
from config import CLIENT_SECRETS_FILE, GOOGLE_SCOPES

# ── In-memory session ────────────────────────────────────────────────────────

_current_session: dict | None = None   # {"email": ..., "token": ...}


def get_session() -> dict | None:
    """Return the currently logged-in session dict, or None."""
    return _current_session


def is_authenticated() -> bool:
    return _current_session is not None


def get_jwt() -> str | None:
    """Return the JWT bearer token if logged in."""
    if _current_session:
        return _current_session.get("token")
    return None


def set_session(session: dict) -> None:
    global _current_session
    _current_session = session


def clear_session() -> None:
    global _current_session
    _current_session = None


# ── Helpers ──────────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def validate_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email))


# ── Email / Password (delegated to backend API) ─────────────────────────────

def register(email: str, password: str) -> tuple[bool, str]:
    """Register a new account via the backend API."""
    ok, msg, token = api_client.register(email, password)
    if ok and token:
        set_session({"email": email.strip().lower(), "token": token})
    return ok, msg


def login(email: str, password: str) -> tuple[bool, str]:
    """Authenticate via the backend API."""
    ok, msg, token = api_client.login(email, password)
    if ok and token:
        set_session({"email": email.strip().lower(), "token": token})
    return ok, msg


# ── Google OAuth 2.0 ─────────────────────────────────────────────────────────

def google_oauth_available() -> bool:
    """Return True if a client_secret.json is present."""
    return os.path.exists(CLIENT_SECRETS_FILE)


def run_google_oauth() -> tuple[bool, str, str, str]:
    """
    Execute the Google OAuth installed-app flow (blocking).

    Returns (success, access_token, email_hint, error_message).
    The *access_token* is sent to the backend for verification.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        return (
            False, "", "",
            "Google OAuth libraries are not installed.\n"
            "Run:  pip install google-auth google-auth-oauthlib requests",
        )

    if not os.path.exists(CLIENT_SECRETS_FILE):
        return False, "", "", (
            "client_secret.json not found.\n"
            "Place your Google OAuth credentials file in the project folder."
        )

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, scopes=GOOGLE_SCOPES
        )
        creds = flow.run_local_server(port=0, open_browser=True)

        if not creds or not creds.token:
            return False, "", "", "Google OAuth did not return a token."

        # Return the access token — the backend will verify it
        return True, creds.token, "", ""
    except Exception as exc:
        return False, "", "", str(exc)


def complete_google_login(access_token: str) -> tuple[bool, str]:
    """
    Send the Google access token to the backend for verification.
    Returns (success, message).
    """
    ok, msg, jwt_token, email = api_client.google_login(access_token)
    if ok and jwt_token:
        set_session({"email": email or "", "token": jwt_token})
    return ok, msg
