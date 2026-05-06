"""Unit tests for filter_products use case."""

import pandas as pd
import pytest

from offerten_converter.application.filter_products import filter_line_items


@pytest.fixture
def sample_df():
    return pd.DataFrame([
        {
            "product_name": "On Cloud 6 Running Shoe",
            "category": "Schuhe",
            "sku": "ON-CLD6-BLK-42",
            "ean": "7630040567890",
            "color": "Black",
            "notes": None,
            "extra_fields": {},
        },
        {
            "product_name": "Arc'teryx Beta Jacket",
            "category": "Jacken",
            "sku": "ARC-BETA-S",
            "ean": "1234567890123",
            "color": "Blue",
            "notes": None,
            "extra_fields": {},
        },
        {
            "product_name": "Buff Merino Wool Hat",
            "category": "Mützen",
            "sku": "BUFF-MW-RED",
            "ean": "9876543210987",
            "color": "Red",
            "notes": None,
            "extra_fields": {},
        },
    ])


class TestFilterLineItems:
    def test_empty_query_returns_all(self, sample_df):
        result, total = filter_line_items(sample_df, "")
        assert len(result) == 3
        assert total == 3

    def test_whitespace_query_returns_all(self, sample_df):
        result, total = filter_line_items(sample_df, "   ")
        assert len(result) == 3

    def test_exact_substring_match(self, sample_df):
        result, total = filter_line_items(sample_df, "Cloud 6")
        assert len(result) == 1
        assert result.iloc[0]["sku"] == "ON-CLD6-BLK-42"
        assert total == 3

    def test_case_insensitive(self, sample_df):
        result, _ = filter_line_items(sample_df, "cloud 6")
        assert len(result) == 1

    def test_category_match(self, sample_df):
        result, _ = filter_line_items(sample_df, "Jacken")
        assert len(result) == 1
        assert result.iloc[0]["sku"] == "ARC-BETA-S"

    def test_sku_match(self, sample_df):
        result, _ = filter_line_items(sample_df, "BUFF-MW")
        assert len(result) == 1
        assert result.iloc[0]["sku"] == "BUFF-MW-RED"

    def test_multi_term_or_logic(self, sample_df):
        result, _ = filter_line_items(sample_df, "Cloud 6, Jacken")
        assert len(result) == 2

    def test_multi_term_all_match(self, sample_df):
        result, _ = filter_line_items(sample_df, "Cloud 6, Jacken, Mützen")
        assert len(result) == 3

    def test_no_match_returns_empty(self, sample_df):
        result, total = filter_line_items(sample_df, "Völlig unbekannt XYZ999")
        assert len(result) == 0
        assert total == 3

    def test_fuzzy_typo_match(self, sample_df):
        result, _ = filter_line_items(sample_df, "Clod 6")
        assert len(result) == 1

    def test_extra_fields_searched(self):
        df = pd.DataFrame([{
            "product_name": "Generic Shirt",
            "category": "Shirts",
            "sku": "SH-001",
            "ean": None,
            "color": None,
            "notes": None,
            "extra_fields": {"style_no": "SUMMER2024"},
        }])
        result, _ = filter_line_items(df, "SUMMER2024")
        assert len(result) == 1

    def test_comma_only_query_returns_all(self, sample_df):
        result, _ = filter_line_items(sample_df, ",,,")
        assert len(result) == 3

    def test_total_count_is_unfiltered_length(self, sample_df):
        _, total = filter_line_items(sample_df, "Cloud 6")
        assert total == len(sample_df)
