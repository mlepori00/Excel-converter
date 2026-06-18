"""Integration tests for the FastAPI routes.

Uses httpx TestClient – no network, no AI calls (AI extraction mocked).
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from offerten_converter.api.auth import get_current_user
from offerten_converter.api.server import app
from offerten_converter.application.auth import AuthService
from offerten_converter.domain.entities import User
from offerten_converter.infrastructure.db.base import Base
from offerten_converter.infrastructure.db.engine import get_db, make_engine
from offerten_converter.infrastructure.security import BcryptPasswordHasher
from offerten_converter.infrastructure.sql_user_repo import SqlUserRepository

client = TestClient(app)

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _supplier_xlsx_bytes() -> bytes:
    """Small supplier offer whose columns the local heuristic can map."""
    buf = BytesIO()
    pd.DataFrame({
        "SKU": ["DC0774-105", "HJ5996-002"],
        "Bezeichnung": ["Air Jordan 1 Low", "Nike Air Max 95 OG"],
        "Grösse": ["5", "5.5"],
        "EK/Stk": [64.99, 94.99],
        "Max. verfügbar": [25, 42],
        "Währung": ["EUR", "EUR"],
    }).to_excel(buf, index=False)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _archive_env(tmp_path):
    """Authenticated test user + an isolated DB for archiving.

    Phase 1c protects the main router with get_current_user; phase 2b makes the
    export endpoint persist offers via get_db. These route tests exercise the
    business endpoints, so we override both with a fixed user and a temp DB.
    A real user row is seeded so the offer's created_by FK is satisfied.
    Returns the session factory so tests can inspect the archived data.
    Autouse + module-local → does not affect the real auth tests.
    """
    engine = make_engine(f"sqlite:///{tmp_path / 'routes.db'}")
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    seed = TestSession()
    seeded = AuthService(SqlUserRepository(seed), BcryptPasswordHasher()).create_user(
        "test@amp.ch", "Test User", "passwort1"
    )
    seed.close()

    def _override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_current_user] = lambda: User(
        id=seeded.id, email=seeded.email, name=seeded.name, password_hash="x"
    )
    app.dependency_overrides[get_db] = _override_get_db
    yield TestSession
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# GET /api/rates
# ---------------------------------------------------------------------------

def test_rates_live_when_ecb_available():
    with patch(
        "offerten_converter.api.routes.fetch_ecb_rates",
        return_value=({"CHF": 1.0, "EUR": 1.064}, "2026-06-12"),
    ):
        resp = client.get("/api/rates")
    assert resp.status_code == 200
    data = resp.json()
    assert data["live"] is True
    assert data["date"] == "2026-06-12"
    assert data["rates"]["EUR"] == pytest.approx(1.064)
    # Static rates are merged underneath, so currencies missing from ECB still resolve.
    assert "USD" in data["rates"]


def test_rates_fall_back_to_static_when_ecb_down():
    with patch("offerten_converter.api.routes.fetch_ecb_rates", return_value=None):
        resp = client.get("/api/rates")
    assert resp.status_code == 200
    data = resp.json()
    assert data["live"] is False
    assert data["date"] is None
    # EUR must be weaker than CHF in the static fallback (1 CHF = >1 EUR).
    assert data["rates"]["EUR"] > 1.0


# ---------------------------------------------------------------------------
# POST /api/offer/parse
# ---------------------------------------------------------------------------

def test_parse_returns_file_id_and_products():
    resp = client.post(
        "/api/offer/parse",
        files={"file": ("offer.xlsx", BytesIO(_supplier_xlsx_bytes()), _XLSX_MIME)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "file_id" in data
    assert len(data["file_id"]) == 36  # UUID
    assert data["row_count"] > 0
    # The fixture columns are locally extractable
    assert data["extraction_mode"] in ("local", "cache")
    assert len(data["products"]) > 0


def test_parse_invalid_file_returns_error():
    resp = client.post(
        "/api/offer/parse",
        files={"file": ("bad.xlsx", BytesIO(b"not an excel file"), "application/octet-stream")},
    )
    assert resp.status_code in (400, 422, 500)


# ---------------------------------------------------------------------------
# POST /api/offer/extract  (AI mocked)
# ---------------------------------------------------------------------------

def test_extract_with_mocked_ai():
    # First parse to get file_id
    parse_resp = client.post(
        "/api/offer/parse",
        files={"file": ("offer.xlsx", BytesIO(_supplier_xlsx_bytes()), _XLSX_MIME)},
    )
    file_id = parse_resp.json()["file_id"]

    mock_items = [
        {
            "sku": "TEST-001", "ean": None, "product_name": "Test Artikel",
            "size": "M", "color": "Rot", "category": None, "unit_price": 25.0,
            "currency": "EUR", "ordered_qty": None, "available_qty": 10,
            "availability_status": None, "min_qty": None, "discount_pct": None,
            "notes": None, "extra_fields": {},
        }
    ]
    mock_usage = {"input_tokens": 100, "output_tokens": 50}

    with patch(
        "offerten_converter.api.routes.extract_line_items",
        return_value=(mock_items, mock_usage),
    ):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test-123"}):
            resp = client.post(
                "/api/offer/extract",
                json={"file_id": file_id, "force_api": True},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "api"
    assert len(data["products"]) == 1
    assert data["input_tokens"] == 100


def test_extract_raw_fallback_sends_raw_sheet_to_ai():
    """When was_raw_fallback is True the AI receives the raw sheet text and
    an explicit hint about failed layout detection."""
    buf = BytesIO()
    # All rows match the footer filter ("www." in SKU) → _drop_non_product_rows
    # removes every row → raw_fallback triggers.
    pd.DataFrame({
        "SKU": ["www.supplier.com", "www.supplier.com"],
        "Price EUR": ["59.90", "79.90"],
        "Description": ["Red Shirt", "Blue Pants"],
    }).to_excel(buf, index=False)

    parse_resp = client.post(
        "/api/offer/parse",
        files={"file": ("raw_offer.xlsx", BytesIO(buf.getvalue()), _XLSX_MIME)},
    )
    assert parse_resp.status_code == 200
    file_id = parse_resp.json()["file_id"]
    assert parse_resp.json()["layout_type"] == "raw_fallback"

    mock_extract = MagicMock(return_value=([], {"input_tokens": 10, "output_tokens": 5}))

    with patch("offerten_converter.api.routes.extract_line_items", mock_extract):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test-123"}):
            resp = client.post("/api/offer/extract", json={"file_id": file_id})

    assert resp.status_code == 200
    # Inspect the sanitized_text argument (positional arg 0) and hints (arg 1).
    sanitized_text_arg = mock_extract.call_args[0][0]
    hints_str_arg = mock_extract.call_args[0][1]
    assert "RAW SHEET" in sanitized_text_arg
    assert "PROCESSED VIEW" in sanitized_text_arg
    assert "layout detection failed" in hints_str_arg.lower()


def test_extract_unknown_file_id_returns_404():
    resp = client.post(
        "/api/offer/extract",
        json={"file_id": "00000000-0000-0000-0000-000000000000", "force_api": True},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Manual column mapping: /api/offer/column-options + /api/offer/remap
# ---------------------------------------------------------------------------

def _two_price_xlsx() -> bytes:
    """Supplier file with a trade-price column and a second, unaliased price column."""
    buf = BytesIO()
    pd.DataFrame({
        "SKU": ["A-1", "A-2"],
        "Bezeichnung": ["Shoe One", "Shoe Two"],
        "Grösse": ["42", "43"],
        "Max. verfügbar": [10, 20],
        "Cost": [11.0, 22.0],         # 'cost' is a unit_price alias → heuristic picks this
        "Sonderpreis": [9.9, 8.8],    # not an alias → initially unmapped
        "Währung": ["EUR", "EUR"],
    }).to_excel(buf, index=False)
    return buf.getvalue()


def test_column_options_lists_columns_and_current_mapping():
    parse = client.post(
        "/api/offer/parse",
        files={"file": ("offer.xlsx", BytesIO(_two_price_xlsx()), _XLSX_MIME)},
    )
    file_id = parse.json()["file_id"]

    resp = client.post("/api/offer/column-options", json={"file_id": file_id})
    assert resp.status_code == 200
    data = resp.json()
    names = [c["name"] for c in data["columns"]]
    assert "Sonderpreis" in names and "Cost" in names
    assert "unit_price" in data["fields"]
    # The heuristic chose the 'Cost' column for the price.
    assert data["current_mapping"].get("unit_price") == "Cost"
    # Samples are provided for the UI.
    cost_col = next(c for c in data["columns"] if c["name"] == "Cost")
    assert len(cost_col["samples"]) > 0


def test_remap_overrides_price_column():
    parse = client.post(
        "/api/offer/parse",
        files={"file": ("offer.xlsx", BytesIO(_two_price_xlsx()), _XLSX_MIME)},
    )
    file_id = parse.json()["file_id"]

    resp = client.post(
        "/api/offer/remap",
        json={"file_id": file_id, "mapping": {"unit_price": "Sonderpreis"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mapped_fields"]["unit_price"] == "Sonderpreis"
    prices = sorted(float(p["unit_price"]) for p in data["products"] if p["unit_price"] is not None)
    assert prices == [8.8, 9.9]


def _ai_only_sku_xlsx() -> bytes:
    """File whose SKU column name no heuristic alias matches (only the AI mapper finds it),
    plus a colour-code and a colour-name column."""
    buf = BytesIO()
    pd.DataFrame({
        "Hersteller-Nr": ["A-1", "A-2"],   # not a heuristic SKU alias
        "Bezeichnung": ["Shoe One", "Shoe Two"],
        "Farbcode": ["001", "002"],
        "Farbe Text": ["Schwarz", "Weiss"],
        "Grösse": ["42", "43"],
        "Max. verfügbar": [10, 20],
        "Cost": [11.0, 22.0],
        "Währung": ["EUR", "EUR"],
    }).to_excel(buf, index=False)
    return buf.getvalue()


def test_remap_preserves_prior_ai_mapping():
    """Regression: editing one field in the manual dialog must not drop fields that
    only the AI column mapper resolved (e.g. an unaliased SKU column)."""
    parse = client.post(
        "/api/offer/parse",
        files={"file": ("offer.xlsx", BytesIO(_ai_only_sku_xlsx()), _XLSX_MIME)},
    )
    file_id = parse.json()["file_id"]

    # The heuristic alone does not recognise the SKU column.
    opts = client.post("/api/offer/column-options", json={"file_id": file_id}).json()
    assert "sku" not in opts["current_mapping"]

    # Simulate the AI mapper having resolved it; the dialog now pre-fills SKU too.
    prior = {"sku": "Hersteller-Nr", "color": "Farbcode"}
    opts2 = client.post(
        "/api/offer/column-options",
        json={"file_id": file_id, "prior_mapping": prior},
    ).json()
    assert opts2["current_mapping"].get("sku") == "Hersteller-Nr"

    # User changes only the colour (code → name); SKU must survive.
    resp = client.post(
        "/api/offer/remap",
        json={
            "file_id": file_id,
            "mapping": {**opts2["current_mapping"], "color": "Farbe Text"},
            "prior_mapping": prior,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mapped_fields"]["sku"] == "Hersteller-Nr"
    assert data["mapped_fields"]["color"] == "Farbe Text"
    skus = sorted(p["sku"] for p in data["products"])
    assert skus == ["A-1", "A-2"]
    colors = sorted(p["color"] for p in data["products"])
    assert colors == ["Schwarz", "Weiss"]


def test_remap_unknown_file_id_returns_404():
    resp = client.post(
        "/api/offer/remap",
        json={"file_id": "00000000-0000-0000-0000-000000000000", "mapping": {}},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/offer/export
# ---------------------------------------------------------------------------

def test_export_returns_xlsx():
    payload = {
        "file_id": "irrelevant-for-export",
        "supplier_name": "Test Lieferant",
        "created_by": "AMP Sport GmbH",
        "target_currency": "CHF",
        "valid_days": 30,
        "default_margin_pct": 40.0,
        "rows": [
            {
                "sku": "SKU-001",
                "product_name": "Test Artikel",
                "size": "M",
                "color": "Blau",
                "unit_price": 50.0,
                "currency": "EUR",
                "ordered_qty": 10,
                "margin_pct": 40.0,
            }
        ],
    }
    resp = client.post("/api/offer/export", json=payload)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(resp.content) > 1000  # real xlsx, not empty


def test_export_archives_offer(_archive_env):
    from offerten_converter.domain.entities import OfferStatus
    from offerten_converter.infrastructure.sql_offer_repo import SqlOfferRepository

    payload = {
        "file_id": "irrelevant-for-export",
        "supplier_name": "Test Lieferant",
        "marke": "Nike",
        "target_currency": "CHF",
        "default_margin_pct": 40.0,
        "rows": [
            {
                "sku": "SKU-001",
                "product_name": "Test Artikel",
                "unit_price": 50.0,
                "currency": "EUR",
                "ordered_qty": 10,
                "margin_pct": 40.0,
            }
        ],
    }
    resp = client.post("/api/offer/export", json=payload)
    assert resp.status_code == 200
    assert "X-Offer-Id" in resp.headers

    offer_id = int(resp.headers["X-Offer-Id"])
    saved = SqlOfferRepository(_archive_env()).get(offer_id)
    assert saved is not None
    assert saved.marke == "Nike"
    assert saved.lieferant == "Test Lieferant"
    assert saved.created_by_name == "Test User"
    assert saved.jahr >= 2025
    assert saved.status is OfferStatus.CREATED
    assert len(saved.line_items) == 1
    assert saved.line_items[0].sku == "SKU-001"
    assert saved.line_items[0].vk_unit is not None  # priced


def test_export_archives_original_file_from_store(_archive_env):
    from offerten_converter.api import file_store
    from offerten_converter.infrastructure.sql_offer_repo import SqlOfferRepository

    file_id = file_store.put(b"SUPPLIER_BYTES", "lieferant.xlsx")
    payload = {
        "file_id": file_id,
        "supplier_name": "Eishockey GmbH",
        "marke": "CCM",
        "rows": [{"sku": "X1", "unit_price": 20.0, "ordered_qty": 5, "margin_pct": 30.0}],
    }
    resp = client.post("/api/offer/export", json=payload)
    assert resp.status_code == 200

    offer_id = int(resp.headers["X-Offer-Id"])
    original = SqlOfferRepository(_archive_env()).get_original_file(offer_id)
    assert original == (b"SUPPLIER_BYTES", "lieferant.xlsx")


def test_export_empty_rows_returns_400():
    resp = client.post(
        "/api/offer/export",
        json={"file_id": "x", "supplier_name": "Test", "rows": []},
    )
    assert resp.status_code == 400


def test_export_missing_supplier_returns_400():
    resp = client.post(
        "/api/offer/export",
        json={
            "file_id": "x",
            "supplier_name": "  ",
            "rows": [{"unit_price": 10.0, "margin_pct": 40.0}],
        },
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/profiles
# ---------------------------------------------------------------------------

def test_list_profiles_returns_list():
    resp = client.get("/api/profiles")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
