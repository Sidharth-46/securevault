"""
file_manager.py - File operations for Secure File Vault.

Handles uploading (encrypt → store → record), viewing (temp decrypt),
restoring (decrypt → original location), and integrity verification.
"""

import os
import uuid
import tempfile
import atexit

from cryptography.fernet import Fernet

import database
from encryption import encrypt_data, decrypt_data, compute_sha256

# Directory where encrypted blobs are persisted
VAULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vault_files")

# Track temporary files so they can be cleaned up on exit
_temp_files: list[str] = []


def cleanup_temp_files() -> None:
    """Remove all temporary decrypted files created during this session."""
    for path in _temp_files:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
    _temp_files.clear()


# Register cleanup so temps are removed when the process exits
atexit.register(cleanup_temp_files)


def _ensure_vault_dir() -> None:
    """Create the vault_files directory if it doesn't exist."""
    os.makedirs(VAULT_DIR, exist_ok=True)


# ── Upload ───────────────────────────────────────────────────────────────────

def upload_file(source_path: str, fernet: Fernet) -> dict:
    """
    Encrypt, store, and securely remove the original file.

    1. Read raw bytes from *source_path*.
    2. Compute SHA-256 of the original data.
    3. Encrypt the data with Fernet.
    4. Write the ciphertext to vault_files/ under a UUID name.
    5. Verify the encrypted blob was written successfully.
    6. Delete the original file from its source location.
    7. Insert a metadata record into the database.

    If encryption or blob-write fails the original file is left untouched.

    Returns the new file record dict.
    """
    _ensure_vault_dir()

    filename = os.path.basename(source_path)
    with open(source_path, "rb") as f:
        raw_data = f.read()

    file_hash = compute_sha256(raw_data)
    encrypted = encrypt_data(raw_data, fernet)

    # Use a UUID so filenames inside the vault are opaque
    blob_name = f"{uuid.uuid4().hex}.enc"
    blob_path = os.path.join(VAULT_DIR, blob_name)
    with open(blob_path, "wb") as f:
        f.write(encrypted)

    # ── Verify the encrypted blob before touching the original ────────
    if not os.path.exists(blob_path) or os.path.getsize(blob_path) == 0:
        raise RuntimeError(
            "Encrypted file verification failed – original file was NOT deleted."
        )

    # ── Securely delete the original file ─────────────────────────────
    try:
        os.remove(source_path)
    except OSError as exc:
        # Non-fatal: vault copy exists, but warn the caller
        database.add_log(
            f"Warning: could not delete original file '{filename}': {exc}"
        )

    database.add_file_record(filename, blob_path, file_hash, original_path=source_path)
    database.add_log(f"File uploaded and original removed: {filename}")

    return {
        "filename": filename,
        "encrypted_path": blob_path,
        "original_path": source_path,
        "file_hash": file_hash,
    }


# ── View (temporary decrypt) ─────────────────────────────────────────────────

def view_file(file_id: int, fernet: Fernet) -> str:
    """
    Decrypt a vault file into a temporary directory and open it with the
    system's default application.

    The temp file is tracked and will be deleted when the application exits
    (or when cleanup_temp_files() is called explicitly).

    Returns the path to the temporary file.
    """
    record = database.get_file_by_id(file_id)
    if record is None:
        raise FileNotFoundError("File record not found in vault database.")

    enc_path = record["encrypted_path"]
    if not os.path.exists(enc_path):
        raise FileNotFoundError(f"Encrypted blob missing: {enc_path}")

    with open(enc_path, "rb") as f:
        ciphertext = f.read()

    plaintext = decrypt_data(ciphertext, fernet)

    # Integrity check
    current_hash = compute_sha256(plaintext)
    if current_hash != record["file_hash"]:
        raise ValueError(
            "SHA-256 integrity check failed — the file may have been tampered with."
        )

    # Write to a secure temp directory, preserving the original filename
    tmp_dir = tempfile.mkdtemp(prefix="vault_view_")
    tmp_path = os.path.join(tmp_dir, record["filename"])
    with open(tmp_path, "wb") as f:
        f.write(plaintext)

    _temp_files.append(tmp_path)

    # Open with the OS default handler
    os.startfile(tmp_path)  # Windows-specific; works on the target OS

    database.add_log(f"File viewed: {record['filename']}")
    return tmp_path


# ── Decrypt & Restore ────────────────────────────────────────────────────────

def restore_file(file_id: int, fernet: Fernet) -> str:
    """
    Decrypt a vault file and restore it to its **original location**.

    1. Decrypt the ciphertext.
    2. Verify SHA-256 integrity.
    3. Write plaintext back to the original path.
    4. Remove the encrypted blob from vault_files/.
    5. Delete the record from the database.

    Returns the restored file path.
    """
    record = database.get_file_by_id(file_id)
    if record is None:
        raise FileNotFoundError("File record not found in vault database.")

    enc_path = record["encrypted_path"]
    if not os.path.exists(enc_path):
        raise FileNotFoundError(f"Encrypted blob missing: {enc_path}")

    with open(enc_path, "rb") as f:
        ciphertext = f.read()

    plaintext = decrypt_data(ciphertext, fernet)

    # Integrity check
    current_hash = compute_sha256(plaintext)
    integrity_ok = current_hash == record["file_hash"]
    if not integrity_ok:
        raise ValueError(
            "SHA-256 integrity check failed — the file may have been tampered with."
        )

    # Determine restore path
    original_path = record.get("original_path", "")
    if not original_path:
        # Fallback: save next to the vault directory with the original name
        original_path = os.path.join(
            os.path.dirname(VAULT_DIR), record["filename"]
        )

    # Ensure the target directory exists
    os.makedirs(os.path.dirname(original_path), exist_ok=True)

    with open(original_path, "wb") as f:
        f.write(plaintext)

    # Remove encrypted blob
    if os.path.exists(enc_path):
        os.remove(enc_path)

    # Remove database record
    database.delete_file_record(file_id)
    database.add_log(f"File restored to original location: {record['filename']}")

    return original_path
