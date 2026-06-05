"""Integration tests for the archive API (phase 2c)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from offerten_converter.api.archive_routes import get_renderer
from offerten_converter.api.auth import get_current_user
from offerten_converter.api.server import app
from offerten_converter.application.ports import SpreadsheetPreviewRenderer
from offerten_converter.domain.entities import Offer, OfferLine, OfferStatus, User
from offerten_converter.infrastructure.db.base import Base
from offerten_converter.infrastructure.db.engine import get_db, make_engine
from offerten_converter.infrastructure.sql_offer_repo import SqlOfferRepository


class _FakeRenderer(SpreadsheetPreviewRenderer):
    """Records calls and returns a deterministic fake HTML document."""

    def __init__(self) -> None:
        self.calls = 0

    def to_html(self, data: bytes, *, src_suffix: str) -> str:
        self.calls += 1
        return f"<html><body>fake {data.decode(errors='replace')}</body></html>"


def _offer(*, jahr, marke, lieferant, status=OfferStatus.CREATED, lines=None):
    return Offer(
        jahr=jahr,
        marke=marke,
        lieferant=lieferant,
        created_by_name="Michele",
        target_currency="CHF",
        default_margin=40.0,
        original_filename=f"{lieferant}.xlsx",
        generated_filename=f"Offerte_{marke}.xlsx",
        status=status,
        line_items=lines or [],
    )


@pytest.fixture
def client(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'archive.db'}")
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    repo = SqlOfferRepository(TestSession())
    repo.create(
        _offer(jahr=2026, marke="Nike", lieferant="Distri A",
               lines=[OfferLine(position=0, sku="N1", product_name="Schuh", vk_unit=80.0)]),
        b"orig-nike-a", b"gen-nike-a",
    )
    repo.create(_offer(jahr=2026, marke="Nike", lieferant="Distri B"), b"o", b"g")
    repo.create(_offer(jahr=2025, marke="CCM", lieferant="Eishockey GmbH",
                       status=OfferStatus.SENT), b"o", b"g")

    def _get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_current_user] = lambda: User(
        id=1, email="t@amp.ch", name="Tester", password_hash="x"
    )
    app.dependency_overrides[get_db] = _get_db
    fake_renderer = _FakeRenderer()
    app.state.fake_renderer = fake_renderer
    app.dependency_overrides[get_renderer] = lambda: fake_renderer
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_renderer, None)


def test_list_all(client):
    resp = client.get("/api/offers")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_list_filters(client):
    assert len(client.get("/api/offers?jahr=2026").json()) == 2
    assert len(client.get("/api/offers?marke=Nike").json()) == 2
    assert len(client.get("/api/offers?marke=Nike&lieferant=Distri B").json()) == 1
    assert len(client.get("/api/offers?status=versendet").json()) == 1
    assert len(client.get("/api/offers?q=eishockey").json()) == 1


def test_list_invalid_status_is_400(client):
    assert client.get("/api/offers?status=quatsch").status_code == 400


def test_tree(client):
    tree = client.get("/api/offers/tree").json()
    # newest year first
    assert [y["jahr"] for y in tree] == [2026, 2025]
    y2026 = tree[0]
    assert y2026["count"] == 2
    assert [m["marke"] for m in y2026["marken"]] == ["Nike"]
    nike = y2026["marken"][0]
    assert nike["count"] == 2
    assert {s["lieferant"] for s in nike["lieferanten"]} == {"Distri A", "Distri B"}


def test_detail_includes_line_items(client):
    offer_id = client.get("/api/offers?marke=Nike&lieferant=Distri A").json()[0]["id"]
    detail = client.get(f"/api/offers/{offer_id}").json()
    assert detail["marke"] == "Nike"
    assert len(detail["line_items"]) == 1
    assert detail["line_items"][0]["sku"] == "N1"
    assert detail["line_items"][0]["vk_unit"] == 80.0


def test_detail_404(client):
    assert client.get("/api/offers/9999").status_code == 404


def test_download_generated(client):
    offer_id = client.get("/api/offers?marke=Nike&lieferant=Distri A").json()[0]["id"]
    resp = client.get(f"/api/offers/{offer_id}/generated")
    assert resp.status_code == 200
    assert resp.content == b"gen-nike-a"


def test_download_original(client):
    offer_id = client.get("/api/offers?marke=Nike&lieferant=Distri A").json()[0]["id"]
    resp = client.get(f"/api/offers/{offer_id}/original")
    assert resp.status_code == 200
    assert resp.content == b"orig-nike-a"


def test_status_update(client):
    offer_id = client.get("/api/offers?marke=Nike&lieferant=Distri A").json()[0]["id"]
    resp = client.patch(f"/api/offers/{offer_id}/status", json={"status": "abgeschlossen"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "abgeschlossen"
    assert client.get(f"/api/offers/{offer_id}").json()["status"] == "abgeschlossen"


def test_status_update_invalid(client):
    offer_id = client.get("/api/offers?marke=Nike&lieferant=Distri A").json()[0]["id"]
    assert client.patch(f"/api/offers/{offer_id}/status", json={"status": "xx"}).status_code == 400


def test_status_update_404(client):
    assert client.patch("/api/offers/9999/status", json={"status": "versendet"}).status_code == 404


def _nike_a_id(client):
    return client.get("/api/offers?marke=Nike&lieferant=Distri A").json()[0]["id"]


def test_preview_generated_renders_html(client):
    offer_id = _nike_a_id(client)
    resp = client.get(f"/api/offers/{offer_id}/preview/generated")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "fake gen-nike-a" in resp.text


def test_preview_original_renders_html(client):
    offer_id = _nike_a_id(client)
    resp = client.get(f"/api/offers/{offer_id}/preview/original")
    assert resp.status_code == 200
    assert "fake orig-nike-a" in resp.text


def test_preview_invalid_which_is_404(client):
    offer_id = _nike_a_id(client)
    assert client.get(f"/api/offers/{offer_id}/preview/quatsch").status_code == 404


def test_preview_offer_not_found_is_404(client):
    assert client.get("/api/offers/9999/preview/generated").status_code == 404
