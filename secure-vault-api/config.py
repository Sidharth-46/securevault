"""
config.py - Backend configuration constants.

All secrets / tunables are read from environment variables with sensible
defaults for local development.
"""

from __future__ import annotations

import os

# ── JWT ──────────────────────────────────────────────────────────────────────

JWT_SECRET: str = os.environ.get("VAULT_JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRY_HOURS: int = int(os.environ.get("VAULT_JWT_EXPIRY_HOURS", "24"))

# ── SMTP (email) ────────────────────────────────────────────────────────────

SMTP_HOST: str = os.environ.get("VAULT_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(os.environ.get("VAULT_SMTP_PORT", "587"))
SMTP_USER: str = os.environ.get("VAULT_SMTP_USER", "")
SMTP_PASS: str = os.environ.get("VAULT_SMTP_PASS", "")
SMTP_FROM: str = os.environ.get("VAULT_SMTP_FROM", "") or SMTP_USER

# ── Password reset ──────────────────────────────────────────────────────────

RESET_TOKEN_EXPIRY_MINUTES: int = 15
WEB_RESET_BASE_URL: str = os.environ.get(
    "VAULT_WEB_RESET_URL", "https://secure-vault.vercel.app"
)

# ── OTP ─────────────────────────────────────────────────────────────────────

OTP_EXPIRY_MINUTES: int = 5
OTP_MAX_ATTEMPTS: int = 5
RESEND_COOLDOWN_SECONDS: int = 30
RESEND_MAX_ATTEMPTS: int = 5

# ── Google OAuth ─────────────────────────────────────────────────────────────

GOOGLE_TOKEN_INFO_URL: str = "https://www.googleapis.com/oauth2/v3/tokeninfo"
GOOGLE_USERINFO_URL: str = "https://www.googleapis.com/oauth2/v3/userinfo"
