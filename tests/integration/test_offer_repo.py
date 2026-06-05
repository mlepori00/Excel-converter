"""Integration tests for the SqlOfferRepository (phase 2a)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import sessionmaker

from offerten_converter.domain.entities import Offer, OfferLine, OfferStatus
from offerten_converter.infrastructure.db.base import Base
from offerten_converter.infrastructure.db.engine import make_engine
from offerten_converter.infrastructure.sql_offer_repo import SqlOfferRepository


@pytest.fixture
def repo(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'offers.db'}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return SqlOfferRepository(Session())


def _make_offer(*, jahr=2026, marke="Nike", lieferant="Sportdistri AG", status=OfferStatus.CREATED):
    return Offer(
        jahr=jahr,
        marke=marke,
        lieferant=lieferant,
        created_by_name="Michele",
        target_currency="CHF",
        default_margin=40.0,
        original_filename="lieferant.xlsx",
        generated_filename="Offerte_Nike_20260101.xlsx",
        status=status,
        line_items=[
            OfferLine(position=0, sku="A1", ean="111", product_name="Schuh", unit_price=50.0,
                      currency="EUR", ordered_qty=10, vk_unit=80.0, vk_total=800.0,
                      margin_actual=0.4, extra_fields={"Kollektion": "FS26"}),
            OfferLine(position=1, sku="A2", product_name="Socke", unit_price=5.0, currency="EUR"),
        ],
    )


def test_create_and_get_roundtrip(repo):
    saved = repo.create(_make_offer(), b"ORIGINAL_BYTES", b"GENERATED_BYTES")
    assert saved.id is not None

    got = repo.get(saved.id)
    assert got is not None
    assert got.marke == "Nike"
    assert got.lieferant == "Sportdistri AG"
    assert got.jahr == 2026
    assert got.status is OfferStatus.CREATED
    assert len(got.line_items) == 2
    assert got.line_items[0].sku == "A1"
    assert got.line_items[0].extra_fields == {"Kollektion": "FS26"}
    assert got.line_items[0].provenance is None  # filled in phase 3


def test_get_files(repo):
    saved = repo.create(_make_offer(), b"ORIGINAL_BYTES", b"GENERATED_BYTES")
    orig = repo.get_original_file(saved.id)
    gen = repo.get_generated_file(saved.id)
    assert orig == (b"ORIGINAL_BYTES", "lieferant.xlsx")
    assert gen == (b"GENERATED_BYTES", "Offerte_Nike_20260101.xlsx")
    assert repo.get_original_file(9999) is None


def test_list_filters(repo):
    repo.create(_make_offer(jahr=2026, marke="Nike", lieferant="Distri A"), b"o", b"g")
    repo.create(_make_offer(jahr=2026, marke="Nike", lieferant="Distri B"), b"o", b"g")
    repo.create(_make_offer(jahr=2025, marke="CCM", lieferant="Distri C"), b"o", b"g")

    assert len(repo.list()) == 3
    assert len(repo.list(jahr=2026)) == 2
    assert len(repo.list(marke="Nike")) == 2
    assert len(repo.list(marke="Nike", lieferant="Distri B")) == 1
    assert len(repo.list(jahr=2025)) == 1
    # list returns metadata only (no line items loaded)
    assert repo.list(jahr=2025)[0].line_items == []


def test_list_query_freetext(repo):
    repo.create(_make_offer(marke="Nike", lieferant="Sportdistri AG"), b"o", b"g")
    repo.create(_make_offer(marke="CCM", lieferant="Eishockey GmbH"), b"o", b"g")
    assert len(repo.list(query="sportdistri")) == 1
    assert len(repo.list(query="gmbh")) == 1
    assert len(repo.list(query="zzz")) == 0


def test_update_status(repo):
    saved = repo.create(_make_offer(), b"o", b"g")
    updated = repo.update_status(saved.id, OfferStatus.SENT)
    assert updated is not None
    assert updated.status is OfferStatus.SENT
    assert repo.get(saved.id).status is OfferStatus.SENT
    assert repo.update_status(9999, OfferStatus.SENT) is None
