"""
config.py - Backend configuration constants.

All secrets and tunables are read from environment variables.
Locally, values are loaded from a ``.env`` file via *python-dotenv*.
In production (Render / Railway) set them in the platform dashboard.

Never commit real credentials.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()  # reads .env in the project root (no-op if file is absent)

# ── JWT ──────────────────────────────────────────────────────────────────────

JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRY_HOURS: int = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

# ── Email / SMTP ─────────────────────────────────────────────────────────────

SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
EMAIL_USER: str = os.getenv("EMAIL_USER", "")
EMAIL_PASS: str = os.getenv("EMAIL_PASS", "")
EMAIL_FROM: str = os.getenv("EMAIL_FROM", "") or EMAIL_USER

# ── Password reset ──────────────────────────────────────────────────────────

RESET_TOKEN_EXPIRY_MINUTES: int = 15
RESET_WEB_URL: str = os.getenv("RESET_WEB_URL", "https://securevaultsid.vercel.app")

# ── OTP ──────────────────────────────────────────────────────────────────────

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

GOOGLE_USERINFO_URL: str = "https://www.googleapis.com/oauth2/v3/userinfo"

# ── Startup validation ──────────────────────────────────────────────────────


def validate_config() -> None:
    """Raise `RuntimeError` if critical environment variables are missing."""
    missing: list[str] = []
    if not EMAIL_USER:
        missing.append("EMAIL_USER")
    if not EMAIL_PASS:
        missing.append("EMAIL_PASS")
    if not RESET_WEB_URL:
        missing.append("RESET_WEB_URL")
    if not FIREBASE_SERVICE_ACCOUNT_PATH:
        missing.append("FIREBASE_SERVICE_ACCOUNT_PATH")
    if JWT_SECRET == "change-me-in-production":
        import logging
        logging.getLogger("securevault.config").warning(
            "JWT_SECRET is still the default placeholder — set it in production!"
        )
    if missing:
        raise RuntimeError(
            "Missing required environment variables: %s. "
            "Set them in .env (local) or in your hosting dashboard (production)."
            % ", ".join(missing)
        )
