"""Integration tests for the pricing enrichment pipeline."""

import pandas as pd
import pytest

from offerten_converter.application.calculate_prices import enrich_dataframe


class TestEnrichDataframe:
    def test_adds_all_columns(self, sample_line_items_df):
        result = enrich_dataframe(sample_line_items_df, 40.0, "CHF")
        expected_columns = [
            "qty",
            "ek_unit_target",
            "ek_target",
            "vk_unit_target",
            "vk_target",
            "margin_actual",
            "margin_color_val",
        ]
        for col in expected_columns:
            assert col in result.columns

    def test_discount_applied(self):
        df = pd.DataFrame([{
            "unit_price": 100.0, "currency": "CHF", "discount_pct": 10.0,
            "ordered_qty": 1, "min_qty": None,
        }])
        result = enrich_dataframe(df, 40.0, "CHF")
        # Unit price after 10% discount = 90.0
        assert result.iloc[0]["ek_unit_target"] == pytest.approx(90.0, rel=1e-3)
        # Total = unit × qty(1) = 90.0
        assert result.iloc[0]["ek_target"] == pytest.approx(90.0, rel=1e-3)

    def test_lot_multiplier(self):
        df = pd.DataFrame([{
            "unit_price": 24.90, "currency": "EUR", "discount_pct": 5.0,
            "ordered_qty": 10, "min_qty": None,
        }])
        result = enrich_dataframe(df, 40.0, "CHF")
        # Total = unit × 10, converted to CHF
        assert result.iloc[0]["qty"] == 10
        assert result.iloc[0]["ek_target"] == pytest.approx(
            result.iloc[0]["ek_unit_target"] * 10, rel=1e-3
        )

    def test_manual_vk_override(self):
        df = pd.DataFrame([{
            "unit_price": 100.0, "currency": "CHF", "discount_pct": 0.0,
            "ordered_qty": 1, "min_qty": None, "vk_target": 200.0,
        }])
        result = enrich_dataframe(df, 40.0, "CHF")
        # Manual VK is per-unit; with qty=1, total equals unit
        assert result.iloc[0]["vk_unit_target"] == pytest.approx(200.0)
        assert result.iloc[0]["vk_target"] == pytest.approx(200.0)
        assert result.iloc[0]["margin_actual"] == pytest.approx(50.0, rel=1e-1)

    def test_margin_color_green(self, sample_line_items_df):
        result = enrich_dataframe(sample_line_items_df, 40.0, "CHF")
        assert all(c == "green" for c in result["margin_color_val"])
