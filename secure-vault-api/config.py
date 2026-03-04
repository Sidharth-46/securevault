"""
config.py - Backend configuration constants.

All secrets and tunables are read from environment variables.
Never commit real credentials — set them in your hosting platform's
environment-variable settings (Render, Railway, etc.).
"""

from __future__ import annotations

import os

# ── JWT ──────────────────────────────────────────────────────────────────────

JWT_SECRET: str = os.getenv("VAULT_JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRY_HOURS: int = int(os.getenv("VAULT_JWT_EXPIRY_HOURS", "24"))

# ── SMTP (email) ────────────────────────────────────────────────────────────

SMTP_HOST: str = os.getenv("VAULT_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(os.getenv("VAULT_SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("VAULT_SMTP_USER", "")
SMTP_PASS: str = os.getenv("VAULT_SMTP_PASS", "")
SMTP_FROM: str = os.getenv("VAULT_SMTP_FROM", "") or SMTP_USER

# ── Password reset ──────────────────────────────────────────────────────────

RESET_TOKEN_EXPIRY_MINUTES: int = 15
WEB_RESET_BASE_URL: str = os.getenv(
    "VAULT_WEB_RESET_URL", "https://securevaultsid.vercel.app"
)

# ── OTP ─────────────────────────────────────────────────────────────────────

OTP_EXPIRY_MINUTES: int = 5
OTP_MAX_ATTEMPTS: int = 5
RESEND_COOLDOWN_SECONDS: int = 30
RESEND_MAX_ATTEMPTS: int = 5

# ── Firebase ─────────────────────────────────────────────────────────────────

FIREBASE_SERVICE_ACCOUNT_PATH: str = os.getenv(
    "FIREBASE_SERVICE_ACCOUNT_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "firebase_service_account.json"),
)

# ── Google OAuth ─────────────────────────────────────────────────────────────

GOOGLE_TOKEN_INFO_URL: str = "https://www.googleapis.com/oauth2/v3/tokeninfo"
GOOGLE_USERINFO_URL: str = "https://www.googleapis.com/oauth2/v3/userinfo"
