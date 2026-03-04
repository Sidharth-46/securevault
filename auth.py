"""
auth.py - Vault master-password module for Secure File Vault.

Responsibilities:
  • Hashing vault master passwords with bcrypt
  • Verifying vault passwords against stored hashes
  • Coordinating vault credential creation with the local database

Note: This is separate from user-account authentication, which is
handled by the backend API via auth_service.py / api_client.py.
"""

import base64

import bcrypt

import database
from encryption import generate_salt


# ── Password Hashing ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash *password* with bcrypt and return the hash as a UTF-8 string."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Return True if *password* matches the bcrypt *hashed* value."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ── Registration & Login ─────────────────────────────────────────────────────

def is_first_launch() -> bool:
    """Check whether a master user has been created yet."""
    return database.get_user() is None


def register_user(password: str) -> bytes:
    """
    Register the master user:
      1. Hash the password with bcrypt.
      2. Generate a random salt for key derivation.
      3. Store the hash and salt in the database.

    Returns the raw salt bytes (needed to derive the encryption key).
    """
    pw_hash = hash_password(password)
    salt = generate_salt()
    salt_b64 = base64.b64encode(salt).decode()  # store salt as base64 text
    database.create_user(pw_hash, salt_b64)
    database.add_log("Master password created")
    return salt


def login(password: str) -> tuple[bool, bytes | None]:
    """
    Attempt to authenticate with *password*.

    Returns (success, salt_bytes | None).
    On failure a log entry is recorded.
    """
    user = database.get_user()
    if user is None:
        return False, None

    if verify_password(password, user["password_hash"]):
        salt = base64.b64decode(user["salt"])
        database.add_log("Successful login")
        return True, salt

    database.add_log("Failed login attempt")
    return False, None
