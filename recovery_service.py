"""
recovery_service.py - Account recovery for Secure File Vault.

All recovery logic (password reset tokens, OTP generation, email sending)
is now handled by the backend API.  This module is a thin wrapper around
``api_client`` so the UI code can continue calling the same function names.
"""

from __future__ import annotations

import api_client
from config import RESEND_COOLDOWN_SECONDS  # re-export for UI cooldown timer

# ── Constant re-exports expected by the UI ───────────────────────────────────
# The UI references ``recovery_service.RESEND_COOLDOWN_SECONDS`` for the local
# countdown timer, so we surface the value from config.

# ═════════════════════════════════════════════════════════════════════════════
#  FORGOT PASSWORD
# ═════════════════════════════════════════════════════════════════════════════

def request_password_reset(email: str) -> tuple[bool, str]:
    """Ask the backend to generate a reset token and send the reset email."""
    return api_client.forgot_password(email)


def resend_password_reset(email: str) -> tuple[bool, str]:
    """Re-send the password reset email (backend enforces cooldown)."""
    return api_client.forgot_password(email)


def reset_password(token: str, new_password: str) -> tuple[bool, str]:
    """Submit a reset token + new password to the backend."""
    return api_client.reset_password(token, new_password)


# ═════════════════════════════════════════════════════════════════════════════
#  FORGOT MASTER PIN (OTP-protected)
# ═════════════════════════════════════════════════════════════════════════════

def request_master_pin_otp(email: str) -> tuple[bool, str]:
    """Ask the backend to generate and email a 6-digit OTP."""
    return api_client.request_otp(email)


def resend_otp(email: str) -> tuple[bool, str]:
    """Re-send the OTP (backend enforces cooldown)."""
    return api_client.resend_otp(email)


def verify_otp(email: str, otp_input: str) -> tuple[bool, str]:
    """Validate an OTP entered by the user."""
    return api_client.verify_otp(email, otp_input)


def reset_master_pin(email: str, new_pin: str) -> tuple[bool, str]:
    """Reset the master PIN after OTP verification."""
    return api_client.reset_master_pin(email, new_pin)


# ── Cooldown helper (used by the local UI timer) ────────────────────────────

def get_resend_cooldown_remaining(_email: str) -> int:
    """Return the cooldown value.

    The real cooldown is enforced server-side; the desktop app only needs a
    fixed constant to drive its local countdown animation.
    """
    return RESEND_COOLDOWN_SECONDS
