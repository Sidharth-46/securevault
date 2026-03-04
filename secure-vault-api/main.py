"""
main.py - FastAPI backend for Secure File Vault.

Run with:
    uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.auth_routes import router as auth_router
from routes.reset_routes import router as reset_router

app = FastAPI(
    title="Secure File Vault API",
    version="1.0.0",
    description="Backend authentication service for Secure File Vault.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(reset_router)


@app.get("/")
def root():
    return {"status": "ok", "service": "Secure File Vault API"}
