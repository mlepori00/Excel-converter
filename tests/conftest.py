"""Shared test fixtures for the Offerten Converter test suite."""

import pandas as pd
import pytest


@pytest.fixture
def sample_line_items_df():
    """DataFrame mimicking Claude extraction output."""
    return pd.DataFrame([
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


@pytest.fixture
def sample_enriched_df(sample_line_items_df):
    """Enriched DataFrame with pricing columns added."""
    df = sample_line_items_df.copy()
    df["qty"] = [10, 6]
    df["ek_unit_target"] = [24.77, 13.51]
    df["ek_target"] = [247.70, 81.05]
    df["vk_unit_target"] = [41.28, 22.51]
    df["vk_target"] = [412.83, 135.08]
    df["margin_actual"] = [0.40, 0.40]
    df["margin_color_val"] = ["green", "green"]
    return df


@pytest.fixture
def sample_supplier_profile():
    """Supplier profile dict."""
    return {
        "name": "Test Supplier",
        "typical_currency": "EUR",
        "typical_discount": 5.0,
        "column_hints": "sku=Artikelnr, price=Einzelpreis",
    }


@pytest.fixture
def mock_ai_response_json():
    """Realistic Claude extraction response as JSON string."""
    return """[
        {
            "sku": "CCM-TASV-SR-75",
            "ean": "0778235400800",
            "product_name": "Tacks AS-V Pro Senior Skate",
            "size": "7.5 EE",
            "color": null,
            "category": "Schlittschuhe",
            "unit_price": 599.994,
            "currency": "USD",
            "ordered_qty": 1,
            "min_qty": null,
            "discount_pct": 40,
            "notes": null
        }
    ]"""
