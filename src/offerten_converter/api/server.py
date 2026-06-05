"""FastAPI entry point for the AMP Offerten Converter backend.

Start with:
    uvicorn offerten_converter.api.server:app --reload --port 8000
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

_SRC = str(Path(__file__).resolve().parents[3])
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env", override=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

from offerten_converter.api.archive_routes import router as archive_router  # noqa: E402
from offerten_converter.api.auth import get_current_user  # noqa: E402
from offerten_converter.api.auth import router as auth_router  # noqa: E402
from offerten_converter.api.routes import router  # noqa: E402
from offerten_converter.infrastructure.db.engine import init_db  # noqa: E402


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

# Auth router is public (no guard) so /api/auth/login is reachable.
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])

# Every other /api/* route requires a logged-in user (valid Bearer JWT).
app.include_router(router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(archive_router, prefix="/api", dependencies=[Depends(get_current_user)])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# Serve built React frontend if dist/ exists (Docker / production).
# In local dev, Vite handles the frontend separately.
_DIST = _PROJECT_ROOT / "frontend" / "dist"
if _DIST.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="static")
