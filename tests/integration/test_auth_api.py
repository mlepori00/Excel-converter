"""Integration tests for the auth API (login, /me) against a temp database."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from offerten_converter.api.server import app
from offerten_converter.application.auth import AuthService
from offerten_converter.infrastructure.db.base import Base
from offerten_converter.infrastructure.db.engine import get_db, make_engine
from offerten_converter.infrastructure.security import BcryptPasswordHasher
from offerten_converter.infrastructure.sql_user_repo import SqlUserRepository


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient wired to an isolated SQLite database with one seeded user."""
    monkeypatch.delenv("API_SECRET_TOKEN", raising=False)
    engine = make_engine(f"sqlite:///{tmp_path / 'auth.db'}")
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    # Seed a user.
    session = TestSession()
    AuthService(SqlUserRepository(session), BcryptPasswordHasher()).create_user(
        "Anna@Example.CH", "Anna", "geheim123"
    )
    session.close()

    def _override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_login_success_returns_token_and_user(client):
    resp = client.post(
        "/api/auth/login", json={"email": "anna@example.ch", "password": "geheim123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "anna@example.ch"
    assert body["user"]["name"] == "Anna"
    assert "password_hash" not in body["user"]


def test_login_is_case_insensitive_on_email(client):
    resp = client.post(
        "/api/auth/login", json={"email": "ANNA@EXAMPLE.CH", "password": "geheim123"}
    )
    assert resp.status_code == 200


def test_login_wrong_password_is_401(client):
    resp = client.post("/api/auth/login", json={"email": "anna@example.ch", "password": "falsch"})
    assert resp.status_code == 401


def test_login_unknown_user_is_401(client):
    resp = client.post("/api/auth/login", json={"email": "nobody@example.ch", "password": "x"})
    assert resp.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_current_user_with_token(client):
    token = client.post(
        "/api/auth/login", json={"email": "anna@example.ch", "password": "geheim123"}
    ).json()["access_token"]
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "anna@example.ch"


def test_me_rejects_garbage_token(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


def _login_token(client) -> str:
    return client.post(
        "/api/auth/login", json={"email": "anna@example.ch", "password": "geheim123"}
    ).json()["access_token"]


def test_protected_route_requires_auth(client):
    # /api/profiles is guarded by get_current_user since phase 1c.
    assert client.get("/api/profiles").status_code == 401


def test_protected_route_reachable_with_token(client):
    token = _login_token(client)
    resp = client.get("/api/profiles", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
