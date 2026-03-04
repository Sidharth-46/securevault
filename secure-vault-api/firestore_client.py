import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

def _init_firebase():
    if firebase_admin._apps:
        return

    firebase_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

    if not firebase_json:
        raise RuntimeError("Firebase credentials not found")

    cred_dict = json.loads(firebase_json)
    cred = credentials.Certificate(cred_dict)

    firebase_admin.initialize_app(cred)

_init_firebase()

db = firestore.client()