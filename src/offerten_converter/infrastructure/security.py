"""Password hashing (bcrypt) and JWT access tokens.

These are transport/credential concerns and live in infrastructure. The
application layer depends only on the PasswordHasher port, never on bcrypt/jwt.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from offerten_converter import config
from offerten_converter.application.ports import PasswordHasher


class BcryptPasswordHasher(PasswordHasher):
    """PasswordHasher implementation backed by bcrypt."""

    def hash(self, plain: str) -> str:
        return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify(self, plain: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except ValueError:
            # Malformed/legacy hash – treat as a failed verification.
            return False


def create_access_token(subject: str) -> str:
    """Issue a signed JWT whose `sub` claim is the user id."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=config.access_token_ttl_minutes()),
    }
    return jwt.encode(payload, config.secret_key(), algorithm=config.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.PyJWTError if invalid/expired."""
    return jwt.decode(token, config.secret_key(), algorithms=[config.JWT_ALGORITHM])
