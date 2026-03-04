"""
api_client.py - HTTP client for the Secure File Vault backend API.

All authentication and recovery operations are delegated to the remote
backend.  This module wraps ``requests`` calls and returns simple
``(success, message, data)`` tuples so the rest of the desktop app
never deals with raw HTTP.
"""

from __future__ import annotations

from typing import Any

import requests

from config import API_BASE_URL

_TIMEOUT = 15  # seconds


# ── Generic helper ───────────────────────────────────────────────────────────

def _post(endpoint: str, payload: dict) -> dict[str, Any]:
    """POST *payload* as JSON to *endpoint* and return the response dict.

    On network / HTTP errors, returns ``{"success": False, "message": "..."}``
    so callers never have to handle exceptions.
    """
    try:
        resp = requests.post(
            f"{API_BASE_URL}{endpoint}",
            json=payload,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        return {
            "success": False,
            "message": "Cannot reach the authentication server. Is the backend running?",
        }
    except requests.Timeout:
        return {"success": False, "message": "Request timed out. Try again."}
    except requests.HTTPError as exc:
        try:
            body = exc.response.json()
            return {"success": False, "message": body.get("detail", str(exc))}
        except Exception:
            return {"success": False, "message": str(exc)}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


# ═════════════════════════════════════════════════════════════════════════════
#  AUTH
# ═════════════════════════════════════════════════════════════════════════════

def register(email: str, password: str) -> tuple[bool, str, str | None]:
    """Register a new account.  Returns ``(success, message, jwt_token)``."""
    data = _post("/register", {"email": email, "password": password})
    return data.get("success", False), data.get("message", ""), data.get("token")


def login(email: str, password: str) -> tuple[bool, str, str | None]:
    """Authenticate with email + password.  Returns ``(success, msg, jwt)``."""
    data = _post("/login", {"email": email, "password": password})
    return data.get("success", False), data.get("message", ""), data.get("token")


def google_login(access_token: str) -> tuple[bool, str, str | None, str | None]:
    """Exchange a Google access token.  Returns ``(ok, msg, jwt, email)``."""
    data = _post("/google-login", {"access_token": access_token})
    return (
        data.get("success", False),
        data.get("message", ""),
        data.get("token"),
        data.get("email"),
    )


# ═════════════════════════════════════════════════════════════════════════════
#  PASSWORD RESET
# ═════════════════════════════════════════════════════════════════════════════

def forgot_password(email: str) -> tuple[bool, str]:
    data = _post("/forgot-password", {"email": email})
    return data.get("success", False), data.get("message", "")


def reset_password(token: str, new_password: str) -> tuple[bool, str]:
    data = _post("/reset-password", {"token": token, "new_password": new_password})
    return data.get("success", False), data.get("message", "")


# ═════════════════════════════════════════════════════════════════════════════
#  OTP / MASTER PIN
# ═════════════════════════════════════════════════════════════════════════════

def request_otp(email: str) -> tuple[bool, str]:
    data = _post("/request-otp", {"email": email})
    return data.get("success", False), data.get("message", "")


def resend_otp(email: str) -> tuple[bool, str]:
    data = _post("/resend-otp", {"email": email})
    return data.get("success", False), data.get("message", "")


def verify_otp(email: str, otp: str) -> tuple[bool, str]:
    data = _post("/verify-otp", {"email": email, "otp": otp})
    return data.get("success", False), data.get("message", "")


def reset_master_pin(email: str, new_pin: str) -> tuple[bool, str]:
    data = _post("/reset-master-pin", {"email": email, "new_pin": new_pin})
    return data.get("success", False), data.get("message", "")
