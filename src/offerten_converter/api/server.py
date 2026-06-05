"""FastAPI entry point for the AMP Offerten Converter backend.

Start with:
    uvicorn offerten_converter.api.server:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_SRC = str(Path(__file__).resolve().parents[3])
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env", override=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

from offerten_converter.api.auth import router as auth_router  # noqa: E402
from offerten_converter.api.routes import router  # noqa: E402
from offerten_converter.infrastructure.db.engine import init_db  # noqa: E402

_bearer = HTTPBearer(auto_error=False)


def _require_token(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    expected = os.getenv("API_SECRET_TOKEN", "")
    if not expected:
        return  # token auth disabled when env var not set
    if credentials is None or credentials.credentials != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ungültiges Token")


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Initialise the database (create tables) on startup."""
    init_db()
    yield


app = FastAPI(
    title="AMP Sport Offerten Converter API",
    version="1.0.0",
    description="Converts supplier Excel offers into standardised AMP reseller offers.",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth router is public (no token guard) so /api/auth/login is reachable.
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])

app.include_router(router, prefix="/api", dependencies=[Depends(_require_token)])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# Serve built React frontend if dist/ exists (Docker / production).
# In local dev, Vite handles the frontend separately.
_DIST = _PROJECT_ROOT / "frontend" / "dist"
if _DIST.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="static")
