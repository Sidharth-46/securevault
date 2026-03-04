"""
firestore_client.py - Firebase Firestore client initialisation.

Initialises the Firebase Admin SDK and exposes a Firestore ``db`` instance
for use throughout the backend.

Configuration:
  • Set the environment variable ``GOOGLE_APPLICATION_CREDENTIALS`` to the
    path of your Firebase service-account JSON key file, **or**
  • Place a file named ``firebase_service_account.json`` next to this module.
"""

from __future__ import annotations

import os

import firebase_admin
from firebase_admin import credentials, firestore

_SERVICE_ACCOUNT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "firebase_service_account.json",
)


def _init_firebase() -> None:
    """Initialise the Firebase Admin SDK (idempotent)."""
    if firebase_admin._apps:
        return

    if os.path.exists(_SERVICE_ACCOUNT_FILE):
        cred = credentials.Certificate(_SERVICE_ACCOUNT_FILE)
    elif os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        cred = credentials.ApplicationDefault()
    else:
        raise RuntimeError(
            "Firebase credentials not found. Either place "
            "'firebase_service_account.json' in the secure-vault-api/ "
            "directory or set the GOOGLE_APPLICATION_CREDENTIALS env var."
        )

    firebase_admin.initialize_app(cred)


_init_firebase()

db = firestore.client()
