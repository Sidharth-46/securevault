"""
services/email_service.py - Email sending for password resets and OTPs.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import SMTP_HOST, SMTP_PORT, EMAIL_USER, EMAIL_PASS, EMAIL_FROM

logger = logging.getLogger("securevault.email")

_TIMEOUT = 30  # seconds – generous to survive cloud cold-starts


def _smtp_configured() -> bool:
    return bool(EMAIL_USER and EMAIL_PASS)


def send_email(to: str, subject: str, html_body: str) -> tuple[bool, str]:
    """Send an HTML email via Gmail SMTP.  Returns ``(success, error_message)``."""
    if not _smtp_configured():
        return False, (
            "SMTP not configured. Set EMAIL_USER and EMAIL_PASS environment variables."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html"))

    # Try STARTTLS (port 587) first, then fall back to SSL (port 465)
    errors: list[str] = []

    # ── Attempt 1: STARTTLS ──────────────────────────────────────────────
    if SMTP_PORT == 587 or SMTP_PORT != 465:
        try:
            logger.info("SMTP STARTTLS attempt → %s:%s  to=%s", SMTP_HOST, 587, to)
            ctx = ssl.create_default_context()
            with smtplib.SMTP(SMTP_HOST, 587, timeout=_TIMEOUT) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.ehlo()
                server.login(EMAIL_USER, EMAIL_PASS)
                server.sendmail(EMAIL_FROM, to, msg.as_string())
            logger.info("Email sent (STARTTLS) to %s", to)
            return True, ""
        except Exception as exc:
            errors.append(f"STARTTLS:{exc}")
            logger.warning("STARTTLS failed: %s", exc)

    # ── Attempt 2: SSL ───────────────────────────────────────────────────
    try:
        logger.info("SMTP SSL attempt → %s:%s  to=%s", SMTP_HOST, 465, to)
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, 465, timeout=_TIMEOUT, context=ctx) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_FROM, to, msg.as_string())
        logger.info("Email sent (SSL) to %s", to)
        return True, ""
    except Exception as exc:
        errors.append(f"SSL:{exc}")
        logger.warning("SSL failed: %s", exc)

    combined = " | ".join(errors)
    logger.error("All SMTP attempts failed for %s: %s", to, combined)
    return False, f"Failed to send email: {combined}"


# ── Pre-built emails ────────────────────────────────────────────────────────

def send_reset_email(email: str, reset_link: str, expiry_minutes: int) -> tuple[bool, str]:
    """Send a password-reset link email."""
    subject = "Secure File Vault \u2013 Password Reset"
    body = f"""
    <div style="font-family:Segoe UI,sans-serif;max-width:480px;margin:auto;
                padding:32px;background:#1e293b;border-radius:12px;color:#e2e8f0;">
        <h2 style="color:#6366f1;margin-top:0;">Password Reset</h2>
        <p>We received a request to reset your Secure File Vault password.</p>
        <p>Click the link below to reset your password:</p>
        <div style="margin:16px 0;text-align:center;">
            <a href="{reset_link}"
               style="display:inline-block;padding:14px 28px;background:#6366f1;
                      color:white;border-radius:10px;text-decoration:none;
                      font-weight:bold;font-size:14px;">
                Reset Password
            </a>
        </div>
        <p style="font-size:12px;color:#94a3b8;word-break:break-all;">
            Or copy this link: {reset_link}
        </p>
        <p style="font-size:13px;color:#94a3b8;">
            This link expires in {expiry_minutes} minutes.<br>
            If you did not request this reset, ignore this email.
        </p>
    </div>
    """
    return send_email(email, subject, body)


def send_otp_email(email: str, otp: str, expiry_minutes: int) -> tuple[bool, str]:
    """Send an OTP verification email."""
    subject = "Secure File Vault \u2013 OTP Verification"
    body = f"""
    <div style="font-family:Segoe UI,sans-serif;max-width:480px;margin:auto;
                padding:32px;background:#1e293b;border-radius:12px;color:#e2e8f0;">
        <h2 style="color:#6366f1;margin-top:0;">OTP Verification</h2>
        <p>Your OTP for resetting your Master PIN is:</p>
        <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;
                    padding:16px;font-size:28px;font-family:monospace;text-align:center;
                    letter-spacing:8px;color:#818cf8;margin:16px 0;">
            {otp}
        </div>
        <p style="font-size:13px;color:#94a3b8;">
            This code expires in {expiry_minutes} minutes.
        </p>
    </div>
    """
    return send_email(email, subject, body)
