"""
config.py - Desktop application configuration.

Central place for the backend API URL and other tunables.
"""

from __future__ import annotations

import os

# ── Backend API ──────────────────────────────────────────────────────────────
# Override with the VAULT_API_URL environment variable when deploying.

API_BASE_URL: str = os.environ.get("VAULT_API_URL", "https://securevault-ubnm.onrender.com")

# ── Google OAuth ─────────────────────────────────────────────────────────────

CLIENT_SECRETS_FILE: str = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "client_secret.json"
)

GOOGLE_SCOPES: list[str] = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

# ── Cooldown (local UI timer) ───────────────────────────────────────────────

RESEND_COOLDOWN_SECONDS: int = 30
