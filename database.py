"""
database.py - Local database for Secure File Vault.

Manages a SQLite database with tables for **vault metadata only**:
  • vault_credentials – master-password hash and salt for local Fernet key derivation
  • files  – encrypted-file records (filename, path, hash)
  • logs   – activity log entries

All user-account / authentication data is stored in Firestore via the
backend API.  This module no longer contains any credential storage for
user accounts, password reset tokens, or OTPs.
"""

import sqlite3
import os
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vault.db")


def get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    """Create the local vault-metadata tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # Vault master-password hash + salt (for local Fernet key derivation).
    # This is NOT user-account auth — it protects the local encryption key.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vault_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            encrypted_path TEXT NOT NULL,
            original_path TEXT NOT NULL DEFAULT '',
            date_added TEXT NOT NULL,
            file_hash TEXT NOT NULL
        )
    """)

    # Migration: add original_path column if upgrading from an older schema
    try:
        cursor.execute("ALTER TABLE files ADD COLUMN original_path TEXT NOT NULL DEFAULT ''")
    except Exception:
        pass  # column already exists

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    # ── Migration from old schema ────────────────────────────────────────
    # Copy data from the legacy "users" table into "vault_credentials" if
    # it exists and vault_credentials is empty.
    try:
        existing = cursor.execute(
            "SELECT COUNT(*) FROM vault_credentials"
        ).fetchone()[0]
        if existing == 0:
            cursor.execute(
                "INSERT INTO vault_credentials (password_hash, salt) "
                "SELECT password_hash, salt FROM users LIMIT 1"
            )
    except Exception:
        pass  # legacy table doesn't exist — nothing to migrate

    conn.commit()
    conn.close()


# ── Vault credential operations ──────────────────────────────────────────────

def get_user() -> dict | None:
    """Retrieve the vault master-password record, or None."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM vault_credentials LIMIT 1").fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def create_user(password_hash: str, salt: str) -> None:
    """Insert a vault master-password record."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO vault_credentials (password_hash, salt) VALUES (?, ?)",
        (password_hash, salt),
    )
    conn.commit()
    conn.close()


# ── File operations ──────────────────────────────────────────────────────────

def add_file_record(filename: str, encrypted_path: str, file_hash: str, original_path: str = "") -> None:
    """Insert a file metadata record including the original file path."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO files (filename, encrypted_path, original_path, date_added, file_hash) VALUES (?, ?, ?, ?, ?)",
        (filename, encrypted_path, original_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), file_hash),
    )
    conn.commit()
    conn.close()


def get_all_files() -> list[dict]:
    """Return all stored file records."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM files ORDER BY date_added DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_file_by_id(file_id: int) -> dict | None:
    """Retrieve a single file record by id."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def delete_file_record(file_id: int) -> None:
    """Delete a file record by id."""
    conn = get_connection()
    conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()


# ── Log operations ───────────────────────────────────────────────────────────

def add_log(action: str) -> None:
    """Insert an activity log entry with the current timestamp."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO logs (action, timestamp) VALUES (?, ?)",
        (action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def get_all_logs() -> list[dict]:
    """Return all log entries, newest first."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM logs ORDER BY timestamp DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
