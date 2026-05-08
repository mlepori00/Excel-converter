"""Integration tests for the FastAPI routes.

Uses httpx TestClient – no network, no AI calls (AI extraction mocked).
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from offerten_converter.api.server import app

client = TestClient(app)

_DEMO_DIR = Path(__file__).parents[2] / "demo" / "offerten_architekturen"
_DEMO_FILE = _DEMO_DIR / "1.xlsx"


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# POST /api/offer/parse
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _DEMO_FILE.exists(), reason="Demo file not available")
def test_parse_returns_file_id_and_products():
    with open(_DEMO_FILE, "rb") as fh:
        resp = client.post(
            "/api/offer/parse",
            files={"file": ("1.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "file_id" in data
    assert len(data["file_id"]) == 36  # UUID
    assert data["row_count"] > 0
    # File 1 has local extractable data
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

@pytest.mark.skipif(not _DEMO_FILE.exists(), reason="Demo file not available")
def test_extract_with_mocked_ai():
    # First parse to get file_id
    with open(_DEMO_FILE, "rb") as fh:
        parse_resp = client.post(
            "/api/offer/parse",
            files={"file": ("1.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
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

    with patch("offerten_converter.api.routes.extract_line_items", return_value=(mock_items, mock_usage)):
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


def test_extract_unknown_file_id_returns_404():
    resp = client.post(
        "/api/offer/extract",
        json={"file_id": "00000000-0000-0000-0000-000000000000", "force_api": True},
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


def test_export_empty_rows_returns_400():
    resp = client.post(
        "/api/offer/export",
        json={"file_id": "x", "supplier_name": "Test", "rows": []},
    )
    assert resp.status_code == 400


def test_export_missing_supplier_returns_400():
    resp = client.post(
        "/api/offer/export",
        json={"file_id": "x", "supplier_name": "  ", "rows": [{"unit_price": 10.0, "margin_pct": 40.0}]},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/profiles
# ---------------------------------------------------------------------------

def test_list_profiles_returns_list():
    resp = client.get("/api/profiles")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
