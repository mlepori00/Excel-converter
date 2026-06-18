"""Central runtime configuration, read from environment variables.

Kept deliberately small: a single place to resolve paths and settings so
infrastructure code never reads os.getenv directly. Defaults are chosen so the
app runs out-of-the-box in local dev without any .env present.
"""

from __future__ import annotations

import os
from pathlib import Path

# .../OfferConverterAMP  (config.py lives at src/offerten_converter/config.py)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Durable data lives here (SQLite file, later: blobs). Mounted as a volume in
# production so it survives container redeploys.
DATA_DIR = PROJECT_ROOT / "data"


def database_url() -> str:
    """SQLAlchemy database URL.

    Override via the DATABASE_URL env var (e.g. a Postgres URL later).
    Defaults to a local SQLite file under ./data/offerten.db.
    """
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    return f"sqlite:///{DATA_DIR / 'offerten.db'}"


# --- Authentication -------------------------------------------------------

JWT_ALGORITHM = "HS256"

# Dev fallback so the app runs without config; MUST be overridden in production.
_DEV_SECRET = "dev-insecure-secret-change-me-in-production-please"


def secret_key() -> str:
    """Signing key for JWT access tokens. Set SECRET_KEY in production."""
    import logging
    key = os.getenv("SECRET_KEY")
    if not key:
        logging.getLogger(__name__).warning(
            "SECRET_KEY not set — using insecure dev default. "
            "Set SECRET_KEY in production."
        )
        return _DEV_SECRET
    return key


def access_token_ttl_minutes() -> int:
    """Access-token lifetime in minutes (default: 12 hours / one work day)."""
    return int(os.getenv("ACCESS_TOKEN_TTL_MINUTES", "720"))
