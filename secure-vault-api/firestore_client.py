"""
firestore_client.py - Firebase Firestore client initialisation.

Initialises the Firebase Admin SDK and exposes a Firestore ``db`` instance
for use throughout the backend.

Configuration (checked in order):
  1. ``FIREBASE_SERVICE_ACCOUNT_PATH`` env var → path to JSON key file
  2. ``firebase_service_account.json`` file next to this module
  3. ``GOOGLE_APPLICATION_CREDENTIALS`` env var (Application Default Credentials)
"""

from __future__ import annotations

import logging
import os

import firebase_admin
from firebase_admin import credentials, firestore

from config import FIREBASE_SERVICE_ACCOUNT_PATH

logger = logging.getLogger("securevault.firestore")


def _init_firebase() -> None:
    """Initialise the Firebase Admin SDK (idempotent)."""
    if firebase_admin._apps:
        return

    if os.path.exists(FIREBASE_SERVICE_ACCOUNT_PATH):
        logger.info("Loading Firebase credentials from %s", FIREBASE_SERVICE_ACCOUNT_PATH)
        cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)
    elif os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        logger.info("Using GOOGLE_APPLICATION_CREDENTIALS for Firebase")
        cred = credentials.ApplicationDefault()
    else:
        raise RuntimeError(
            "Firebase credentials not found. Set FIREBASE_SERVICE_ACCOUNT_PATH, "
            "place 'firebase_service_account.json' in the secure-vault-api/ "
            "directory, or set the GOOGLE_APPLICATION_CREDENTIALS env var."
        )

    firebase_admin.initialize_app(cred)
    logger.info("Firebase Admin SDK initialised")


_init_firebase()

db = firestore.client()
