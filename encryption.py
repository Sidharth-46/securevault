"""
encryption.py - Encryption utilities for Secure File Vault.

Handles:
  • Deriving a Fernet key from the master password via PBKDF2-HMAC-SHA256
  • Encrypting and decrypting raw file bytes
  • Computing SHA256 file-integrity hashes
"""

import base64
import hashlib
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


# ── Key Derivation ───────────────────────────────────────────────────────────

def generate_salt() -> bytes:
    """Generate a cryptographically secure random 16-byte salt."""
    return os.urandom(16)


def derive_key(password: str, salt: bytes) -> bytes:
    """
    Derive a Fernet-compatible 32-byte key from *password* and *salt*
    using PBKDF2-HMAC-SHA256 with 480 000 iterations.

    Returns a URL-safe base64-encoded key suitable for Fernet.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def get_fernet(password: str, salt: bytes) -> Fernet:
    """Return a Fernet instance keyed from the master password + salt."""
    key = derive_key(password, salt)
    return Fernet(key)


# ── File Encryption / Decryption ─────────────────────────────────────────────

def encrypt_data(data: bytes, fernet: Fernet) -> bytes:
    """Encrypt raw bytes with Fernet and return the ciphertext."""
    return fernet.encrypt(data)


def decrypt_data(token: bytes, fernet: Fernet) -> bytes:
    """Decrypt a Fernet token and return the original plaintext bytes."""
    return fernet.decrypt(token)


# ── SHA-256 Integrity ────────────────────────────────────────────────────────

def compute_sha256(data: bytes) -> str:
    """Return the hex-digest SHA-256 hash of *data*."""
    return hashlib.sha256(data).hexdigest()
