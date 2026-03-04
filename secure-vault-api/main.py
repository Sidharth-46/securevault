"""
main.py - FastAPI backend for Secure File Vault.

Production:
    uvicorn main:app --host 0.0.0.0 --port 10000

Local development:
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.auth_routes import router as auth_router
from routes.reset_routes import router as reset_router
from config import validate_config

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("securevault")

# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Secure Vault API",
    version="1.0.0",
    description="Backend authentication service for Secure File Vault.",
)

# CORS – allow the Vercel frontend and localhost dev server
_ALLOWED_ORIGINS: list[str] = [
    "https://securevaultsid.vercel.app",
    "http://localhost:3000",
]
# Allow override via env var (comma-separated)
_extra = os.environ.get("VAULT_CORS_ORIGINS", "")
if _extra:
    _ALLOWED_ORIGINS.extend([o.strip() for o in _extra.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(reset_router)


@app.on_event("startup")
def _on_startup() -> None:
    validate_config()
    logger.info("Secure Vault API started")
    logger.info("Allowed CORS origins: %s", _ALLOWED_ORIGINS)


@app.get("/")
def health_check():
    return {"status": "Secure Vault API running"}
