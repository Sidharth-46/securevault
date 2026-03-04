"""
routes/reset_routes.py - Password reset, OTP, and master-PIN endpoints.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter
from pydantic import BaseModel

from firestore_client import db
from services.token_service import generate_reset_token, generate_otp
from services.email_service import send_reset_email, send_otp_email
from config import (
    RESET_TOKEN_EXPIRY_MINUTES,
    RESET_WEB_URL,
    OTP_EXPIRY_MINUTES,
    OTP_MAX_ATTEMPTS,
    RESEND_COOLDOWN_SECONDS,
    RESEND_MAX_ATTEMPTS,
)

logger = logging.getLogger("securevault.reset")
router = APIRouter()


# ── Request / response models ───────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class VerifyOtpRequest(BaseModel):
    email: str
    otp: str


class ResetPinRequest(BaseModel):
    email: str
    new_pin: str


class GenericResponse(BaseModel):
    success: bool
    message: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(value: str) -> str:
    return bcrypt.hashpw(value.encode(), bcrypt.gensalt()).decode()


def _get_user_by_email(email: str) -> tuple[str | None, dict | None]:
    docs = (
        db.collection("users")
        .where("email", "==", email)
        .limit(1)
        .stream()
    )
    for doc in docs:
        return doc.id, doc.to_dict()
    return None, None


# ═════════════════════════════════════════════════════════════════════════════
#  FORGOT PASSWORD / RESET PASSWORD
# ═════════════════════════════════════════════════════════════════════════════

@router.post("/forgot-password", response_model=GenericResponse)
def forgot_password(body: ForgotPasswordRequest):
    email = body.email.strip().lower()
    uid, user = _get_user_by_email(email)
    if user is None:
        return GenericResponse(success=False, message="No account found with this email.")

    token = generate_reset_token()
    expires_at = (_now() + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES)).isoformat()

    # Store in password_resets collection
    db.collection("password_resets").document().set(
        {
            "email": email,
            "token": token,
            "expires_at": expires_at,
            "used": False,
        }
    )

    reset_link = f"{RESET_WEB_URL}/reset-password?token={token}"
    ok, err = send_reset_email(email, reset_link, RESET_TOKEN_EXPIRY_MINUTES)
    if not ok:
        logger.error("Failed to send reset email to %s: %s", email, err)
        return GenericResponse(success=False, message=f"Failed to send email: {err}")

    logger.info("Password reset requested: %s", email)
    return GenericResponse(success=True, message="Reset email sent. Check your inbox.")


@router.post("/reset-password", response_model=GenericResponse)
def reset_password(body: ResetPasswordRequest):
    token = body.token.strip()
    if not token:
        return GenericResponse(success=False, message="Token is required.")

    if len(body.new_password) < 6:
        return GenericResponse(
            success=False, message="Password must be at least 6 characters."
        )

    # Look up token in password_resets collection
    docs = (
        db.collection("password_resets")
        .where("token", "==", token)
        .where("used", "==", False)
        .limit(1)
        .stream()
    )
    reset_doc = None
    reset_data = None
    for doc in docs:
        reset_doc = doc
        reset_data = doc.to_dict()

    if reset_data is None:
        return GenericResponse(
            success=False, message="Invalid or already-used reset token."
        )

    # Check expiry
    expires_at = datetime.fromisoformat(reset_data["expires_at"])
    if _now() > expires_at:
        db.collection("password_resets").document(reset_doc.id).update({"used": True})
        return GenericResponse(
            success=False, message="Reset token has expired. Request a new one."
        )

    email = reset_data["email"]
    uid, user = _get_user_by_email(email)
    if user is None:
        return GenericResponse(success=False, message="Account not found.")

    # Update password and mark token used
    pw_hash = _hash(body.new_password)
    db.collection("users").document(uid).update({"password_hash": pw_hash})
    db.collection("password_resets").document(reset_doc.id).update({"used": True})

    logger.info("Password reset completed: %s", email)
    return GenericResponse(success=True, message="Password reset successful. Please sign in.")


# ═════════════════════════════════════════════════════════════════════════════
#  OTP / MASTER PIN RESET
# ═════════════════════════════════════════════════════════════════════════════

@router.post("/request-otp", response_model=GenericResponse)
def request_otp(body: ForgotPasswordRequest):
    email = body.email.strip().lower()
    uid, user = _get_user_by_email(email)
    if user is None:
        return GenericResponse(success=False, message="No account found with this email.")

    otp = generate_otp()
    expires_at = (_now() + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat()

    db.collection("otp_verifications").document().set(
        {
            "email": email,
            "otp": otp,
            "expires_at": expires_at,
            "attempts": 0,
            "resend_count": 0,
            "last_sent_at": _now().isoformat(),
        }
    )

    ok, err = send_otp_email(email, otp, OTP_EXPIRY_MINUTES)
    if not ok:
        logger.error("Failed to send OTP to %s: %s", email, err)
        return GenericResponse(success=False, message=f"Failed to send OTP email: {err}")

    logger.info("OTP requested: %s", email)
    return GenericResponse(success=True, message="OTP sent to your email.")


@router.post("/resend-otp", response_model=GenericResponse)
def resend_otp(body: ForgotPasswordRequest):
    email = body.email.strip().lower()
    uid, user = _get_user_by_email(email)
    if user is None:
        return GenericResponse(success=False, message="No account found with this email.")

    # Get latest OTP doc for this email
    docs = (
        db.collection("otp_verifications")
        .where("email", "==", email)
        .order_by("last_sent_at", direction="DESCENDING")
        .limit(1)
        .stream()
    )
    otp_doc = None
    otp_data = None
    for doc in docs:
        otp_doc = doc
        otp_data = doc.to_dict()

    if otp_data is None:
        return GenericResponse(success=False, message="No OTP request found. Start recovery again.")

    # Cooldown check
    last_sent = datetime.fromisoformat(otp_data["last_sent_at"])
    elapsed = (_now() - last_sent).total_seconds()
    if elapsed < RESEND_COOLDOWN_SECONDS:
        remaining = RESEND_COOLDOWN_SECONDS - int(elapsed)
        return GenericResponse(
            success=False, message=f"Please wait {remaining}s before resending."
        )

    resend_count = otp_data.get("resend_count", 0)
    if resend_count >= RESEND_MAX_ATTEMPTS:
        return GenericResponse(
            success=False,
            message="Maximum resend attempts reached. Restart the recovery process.",
        )

    otp = generate_otp()
    expires_at = (_now() + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat()

    db.collection("otp_verifications").document(otp_doc.id).update(
        {
            "otp": otp,
            "expires_at": expires_at,
            "attempts": 0,
            "resend_count": resend_count + 1,
            "last_sent_at": _now().isoformat(),
        }
    )

    ok, err = send_otp_email(email, otp, OTP_EXPIRY_MINUTES)
    if not ok:
        return GenericResponse(success=False, message=f"Failed to send OTP email: {err}")

    return GenericResponse(success=True, message="New OTP sent to your email.")


@router.post("/verify-otp", response_model=GenericResponse)
def verify_otp(body: VerifyOtpRequest):
    email = body.email.strip().lower()

    # Get latest OTP doc
    docs = (
        db.collection("otp_verifications")
        .where("email", "==", email)
        .order_by("last_sent_at", direction="DESCENDING")
        .limit(1)
        .stream()
    )
    otp_doc = None
    otp_data = None
    for doc in docs:
        otp_doc = doc
        otp_data = doc.to_dict()

    if otp_data is None:
        return GenericResponse(
            success=False, message="No OTP has been requested. Start recovery again."
        )

    # Check attempts
    attempts = otp_data.get("attempts", 0)
    if attempts >= OTP_MAX_ATTEMPTS:
        db.collection("otp_verifications").document(otp_doc.id).delete()
        return GenericResponse(
            success=False, message="Too many failed attempts. Request a new OTP."
        )

    # Check expiry
    expires_at = datetime.fromisoformat(otp_data["expires_at"])
    if _now() > expires_at:
        db.collection("otp_verifications").document(otp_doc.id).delete()
        return GenericResponse(
            success=False, message="OTP has expired. Request a new one."
        )

    if body.otp.strip() != otp_data["otp"]:
        db.collection("otp_verifications").document(otp_doc.id).update(
            {"attempts": attempts + 1}
        )
        remaining = OTP_MAX_ATTEMPTS - (attempts + 1)
        if remaining <= 0:
            db.collection("otp_verifications").document(otp_doc.id).delete()
            return GenericResponse(
                success=False, message="Too many failed attempts. Request a new OTP."
            )
        return GenericResponse(
            success=False,
            message=f"Incorrect OTP. {remaining} attempt(s) remaining.",
        )

    # OTP verified - clean up
    db.collection("otp_verifications").document(otp_doc.id).delete()
    logger.info("OTP verified: %s", email)
    return GenericResponse(success=True, message="OTP verified successfully.")


@router.post("/reset-master-pin", response_model=GenericResponse)
def reset_master_pin(body: ResetPinRequest):
    email = body.email.strip().lower()
    uid, user = _get_user_by_email(email)
    if user is None:
        return GenericResponse(success=False, message="No account found with this email.")

    if len(body.new_pin) < 4:
        return GenericResponse(
            success=False, message="Master PIN must be at least 4 characters."
        )

    pin_hash = _hash(body.new_pin)
    db.collection("users").document(uid).update({"master_pin_hash": pin_hash})

    logger.info("Master PIN reset completed: %s", email)
    return GenericResponse(success=True, message="Master PIN reset successful.")
