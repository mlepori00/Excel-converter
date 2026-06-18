"""Central runtime configuration, read from environment variables.

Kept deliberately small: a single place to resolve paths and settings so
infrastructure code never reads os.getenv directly. Defaults are chosen so the
app runs out-of-the-box in local dev without any .env present.
"""

from __future__ import annotations

import os
import secrets
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

# Random per-process fallback: safe because it can't be guessed from source code.
# Tokens signed with this key are invalidated on server restart — fine for dev.
# Set SECRET_KEY in production for persistent, cross-restart tokens.
_DEV_SECRET = secrets.token_hex(32)


def _is_dev_env() -> bool:
    """True only in explicit dev/local/test environments (via APP_ENV)."""
    return os.getenv("APP_ENV", "dev").lower() in ("dev", "local", "test")


def secret_key() -> str:
    """Signing key for JWT access tokens.

    In a dev environment (APP_ENV unset/dev/local/test) an ephemeral random key
    is used when SECRET_KEY is missing. In any other environment a missing
    SECRET_KEY is a hard startup error — fail closed instead of silently
    degrading auth (tokens that reset on every restart / break across workers).
    """
    import logging
    key = os.getenv("SECRET_KEY")
    if key:
        return key
    if _is_dev_env():
        logging.getLogger(__name__).warning(
            "SECRET_KEY not set — using an ephemeral dev key. "
            "JWT tokens are invalidated on every restart. Set SECRET_KEY in production."
        )
        return _DEV_SECRET
    raise RuntimeError(
        "SECRET_KEY must be set when APP_ENV is not a dev environment "
        "(dev/local/test). Set SECRET_KEY to a long random value."
    )


def access_token_ttl_minutes() -> int:
    """Access-token lifetime in minutes (default: 12 hours / one work day)."""
    return int(os.getenv("ACCESS_TOKEN_TTL_MINUTES", "720"))
