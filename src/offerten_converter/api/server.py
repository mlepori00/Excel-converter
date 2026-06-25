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
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

_SRC = str(Path(__file__).resolve().parents[3])
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env", override=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

from offerten_converter import config  # noqa: E402
from offerten_converter.api.archive_routes import router as archive_router  # noqa: E402
from offerten_converter.api.auth import require_password_changed  # noqa: E402
from offerten_converter.api.auth import router as auth_router  # noqa: E402
from offerten_converter.api.routes import router  # noqa: E402
from offerten_converter.infrastructure.db.engine import init_db  # noqa: E402

_logger = logging.getLogger(__name__)


def _startup_checks() -> None:
    # Resolve the signing key at boot: warns + uses an ephemeral key in dev, but
    # raises in a non-dev APP_ENV when SECRET_KEY is unset — fail fast at startup
    # instead of on the first login (see config.secret_key).
    config.secret_key()
    if not os.getenv("ANTHROPIC_API_KEY"):
        _logger.warning(
            "ANTHROPIC_API_KEY not set — AI extraction will return HTTP 500. "
            "Set ANTHROPIC_API_KEY to enable Claude-based extraction."
        )


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Initialise the database (create tables) on startup."""
    init_db()
    _startup_checks()
    yield


app = FastAPI(
    title="AMP Sport Offerten Converter API",
    version="1.0.0",
    description="Converts supplier Excel offers into standardised AMP reseller offers.",
    lifespan=_lifespan,
)

# ALLOWED_ORIGINS: comma-separated list of allowed origins (e.g. "https://amp.example.com").
# Defaults to "*" for local dev; always set this in production.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()] or ["*"]
if _allowed_origins == ["*"]:
    _logger.warning(
        "ALLOWED_ORIGINS not set — CORS is open to all origins. "
        "Set ALLOWED_ORIGINS in production."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Generic security headers on every response. Cheap hardening against MIME
# sniffing and clickjacking. HSTS is only emitted in production (it is
# meaningless/undesirable over plain-HTTP local dev) and assumes TLS is
# terminated by the reverse proxy in front of the app.
_IS_PROD = os.getenv("APP_ENV", "dev").lower() not in ("dev", "local", "test")


@app.middleware("http")
async def _security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if _IS_PROD:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


# Auth router is public (no guard) so /api/auth/login is reachable.
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])

# Every other /api/* route requires a logged-in user (valid Bearer JWT) who has
# already changed their initial password (must_change_password enforced here).
app.include_router(router, prefix="/api", dependencies=[Depends(require_password_changed)])
app.include_router(archive_router, prefix="/api", dependencies=[Depends(require_password_changed)])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# Serve built React frontend if dist/ exists (Docker / production).
# In local dev, Vite handles the frontend separately.
_DIST = _PROJECT_ROOT / "frontend" / "dist"
if _DIST.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="static")
