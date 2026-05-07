"""E2E test: sanitize → extract (mocked AI) → price → export."""

from __future__ import annotations

import json

import pandas as pd

from offerten_converter.application.calculate_prices import enrich_dataframe
from offerten_converter.application.export_quotation import export_to_excel
from offerten_converter.application.extract_products import extract_line_items
from offerten_converter.application.sanitize_data import sanitize_dataframe
from offerten_converter.infrastructure.excel_writer import build_excel


def _fake_call_fn(user_content: str, system_prompt: str, api_key: str) -> str:
    """Simulated AI response returning two products."""
    return json.dumps([
        {
            "sku": "BR-STD-001",
            "ean": "4260346270001",
            "product_name": "BLACKROLL STANDARD",
            "size": None,
            "color": "schwarz",
            "category": "Faszienrolle",
            "unit_price": 24.90,
            "currency": "EUR",
            "ordered_qty": 10,
            "min_qty": None,
            "discount_pct": 5.0,
            "notes": None,
        },
        {
            "sku": "BR-MINI-001",
            "ean": "4260346270002",
            "product_name": "BLACKROLL MINI",
            "size": None,
            "color": "grün",
            "category": "Faszienrolle",
            "unit_price": 12.90,
            "currency": "EUR",
            "ordered_qty": 6,
            "min_qty": None,
            "discount_pct": 0.0,
            "notes": "Nachlieferung",
        },
    ])


def test_full_pipeline_sanitize_extract_price_export():
    """Complete pipeline: raw data → sanitized → extracted → priced → Excel bytes."""
    # 1. Build a raw DataFrame as if read from Excel
    raw_df = pd.DataFrame({
        "Artikelnr": ["BR-STD-001", "BR-MINI-001"],
        "Bezeichnung": ["BLACKROLL STANDARD", "BLACKROLL MINI"],
        "Preis": ["24.90", "12.90"],
        "Lieferantenname": ["Sport Muster GmbH", "Sport Muster GmbH"],
        "Email Kontakt": ["info@sportmuster.ch", "bestellung@sportmuster.ch"],
    })

    # 2. Sanitize – must remove supplier name and email columns
    df_clean, log = sanitize_dataframe(raw_df)
    assert "Lieferantenname" not in df_clean.columns
    assert "Email Kontakt" not in df_clean.columns
    assert len(log) >= 2  # at least 2 columns removed

    # 3. Extract – uses mocked AI
    sanitized_text = df_clean.to_string(index=False)
    items, usage = extract_line_items(
        sanitized_text,
        column_hints="",
        api_key="sk-test-fake-key",
        call_fn=_fake_call_fn,
    )
    assert len(items) == 2
    assert items[0]["sku"] == "BR-STD-001"
    assert items[1]["product_name"] == "BLACKROLL MINI"
    assert "input_tokens" in usage

    # 4. Price calculation
    extracted_df = pd.DataFrame(items)
    enriched = enrich_dataframe(
        extracted_df, margin_pct=40.0, target_currency="CHF",
    )
    assert "ek_target" in enriched.columns
    assert "vk_target" in enriched.columns
    assert "margin_actual" in enriched.columns
    assert len(enriched) == 2

    # Check pricing values are reasonable
    for _, row in enriched.iterrows():
        assert row["ek_target"] is not None and row["ek_target"] > 0
        assert row["vk_target"] is not None and row["vk_target"] > row["ek_target"]
        assert row["margin_actual"] is not None and row["margin_actual"] > 0

    # 5. Export to Excel bytes
    excel_bytes = export_to_excel(
        enriched,
        supplier_name="Sport Muster GmbH",
        created_by="Test AG",
        target_currency="CHF",
        valid_days=30,
        build_fn=build_excel,
    )
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 1000  # realistic Excel file size
    # Verify it starts with the ZIP magic bytes (xlsx is a zip archive)
    assert excel_bytes[:2] == b"PK"


def test_pipeline_with_manual_vk_override():
    """Pipeline with manual VK override – manual price should be kept."""
    items = [
        {
            "sku": "TST-001",
            "ean": None,
            "product_name": "Test Product",
            "size": None,
            "color": None,
            "category": "Test",
            "unit_price": 100.0,
            "currency": "CHF",
            "ordered_qty": 1,
            "min_qty": None,
            "discount_pct": 0,
            "notes": None,
        },
    ]
    df = pd.DataFrame(items)
    df["vk_target"] = [250.0]  # manual override

    enriched = enrich_dataframe(df, margin_pct=40.0, target_currency="CHF")
    assert enriched.iloc[0]["vk_target"] == 250.0

    excel_bytes = export_to_excel(
        enriched, "Test Supplier", "Test AG", "CHF", 30, build_fn=build_excel,
    )
    assert isinstance(excel_bytes, bytes)
    assert excel_bytes[:2] == b"PK"


def test_pipeline_pii_scrubbing_in_cells():
    """Ensure PII in cell values is redacted, not just whole columns."""
    raw_df = pd.DataFrame({
        "Artikelnr": ["SKU-001"],
        "Bezeichnung": ["Widget (kontakt: max@example.com)"],
        "Preis": ["50.00"],
    })

    df_clean, log = sanitize_dataframe(raw_df)
    # The email in the cell should be redacted
    cell_logs = [e for e in log if e.startswith("Zelle")]
    assert len(cell_logs) >= 1
    # Verify the email is gone from the cleaned data
    assert "max@example.com" not in df_clean.to_string()
    assert "[REDACTED]" in df_clean.to_string()
