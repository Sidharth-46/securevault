"""
services/email_service.py - Email sending for password resets and OTPs.
"""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM


def _smtp_configured() -> bool:
    return bool(SMTP_USER and SMTP_PASS)


def send_email(to: str, subject: str, html_body: str) -> tuple[bool, str]:
    """Send an HTML email via SMTP.  Returns ``(success, error_message)``."""
    if not _smtp_configured():
        return False, (
            "SMTP not configured. Set VAULT_SMTP_USER and VAULT_SMTP_PASS."
        )
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, to, msg.as_string())

        return True, ""
    except Exception as exc:
        return False, str(exc)


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
