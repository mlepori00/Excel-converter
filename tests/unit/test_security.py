"""Unit tests for password hashing and JWT helpers (no fs, no network)."""

from __future__ import annotations

import jwt
import pytest

from offerten_converter.infrastructure.security import (
    BcryptPasswordHasher,
    create_access_token,
    decode_access_token,
)


def test_password_hash_roundtrip():
    hasher = BcryptPasswordHasher()
    hashed = hasher.hash("s3cret!")
    assert hashed != "s3cret!"
    assert hasher.verify("s3cret!", hashed) is True
    assert hasher.verify("wrong", hashed) is False


def test_password_verify_handles_malformed_hash():
    hasher = BcryptPasswordHasher()
    assert hasher.verify("anything", "not-a-bcrypt-hash") is False


def test_access_token_roundtrip():
    token = create_access_token("42")
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert "exp" in payload


def test_decode_rejects_tampered_token():
    token = create_access_token("1")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token + "tampered")
