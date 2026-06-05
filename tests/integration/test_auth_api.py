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

    # Seed users: Anna (normal) and Max (must change password on first login).
    session = TestSession()
    svc = AuthService(SqlUserRepository(session), BcryptPasswordHasher())
    svc.create_user("Anna@Example.CH", "Anna", "geheim123")
    svc.create_user("max@example.ch", "Max", "temp1234", must_change_password=True)
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


# --- password change (phase 1f) ------------------------------------------

def _login(client, email: str, password: str):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_surfaces_must_change_password(client):
    body = _login(client, "max@example.ch", "temp1234").json()
    assert body["user"]["must_change_password"] is True


def test_normal_user_need_not_change_password(client):
    body = _login(client, "anna@example.ch", "geheim123").json()
    assert body["user"]["must_change_password"] is False


def test_change_password_requires_auth(client):
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": "x", "new_password": "yyyyyyyy"},
    )
    assert resp.status_code == 401


def test_change_password_rejects_wrong_current(client):
    token = _login(client, "max@example.ch", "temp1234").json()["access_token"]
    resp = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "falsch", "new_password": "neuespw123"},
    )
    assert resp.status_code == 400


def test_change_password_rejects_too_short(client):
    token = _login(client, "max@example.ch", "temp1234").json()["access_token"]
    resp = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "temp1234", "new_password": "kurz"},
    )
    assert resp.status_code == 400


def test_change_password_success_clears_flag_and_updates_login(client):
    token = _login(client, "max@example.ch", "temp1234").json()["access_token"]
    resp = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "temp1234", "new_password": "neuespw123"},
    )
    assert resp.status_code == 200
    assert resp.json()["must_change_password"] is False

    # Old password no longer works, new one does, and the flag stays cleared.
    assert _login(client, "max@example.ch", "temp1234").status_code == 401
    after = _login(client, "max@example.ch", "neuespw123")
    assert after.status_code == 200
    assert after.json()["user"]["must_change_password"] is False
