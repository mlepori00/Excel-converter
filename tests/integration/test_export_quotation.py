"""Integration tests for Excel export."""

import io

import pandas as pd
import pytest
from openpyxl import load_workbook

from offerten_converter.infrastructure.excel_writer import OUTPUT_COLUMNS, build_excel


@pytest.fixture
def sample_df():
    return pd.DataFrame([
        {
            "product_name": "BLACKROLL STANDARD",
            "sku": "BR-001",
            "ean": "4260346270001",
            "size": None,
            "color": "schwarz",
            "category": "Faszienrolle",
            "qty": 10,
            "ek_unit_target": 24.77,
            "currency": "EUR",
            "ek_target": 247.70,
            "margin_actual": 40.0,
            "vk_unit_target": 41.28,
            "vk_target": 412.83,
            "notes": None,
        },
    ])


class TestBuildExcel:
    def test_returns_valid_xlsx(self, sample_df):
        data = build_excel(sample_df, "Test GmbH", "Tester", "CHF", 30)
        assert isinstance(data, bytes)
        assert len(data) > 0
        wb = load_workbook(io.BytesIO(data))
        assert "Offerte" in wb.sheetnames

    def test_has_correct_column_count(self, sample_df):
        data = build_excel(sample_df, "Test GmbH", "Tester", "CHF")
        wb = load_workbook(io.BytesIO(data))
        ws = wb["Offerte"]
        header_row = 6
        filled_cols = sum(
            1 for col in range(1, 50) if ws.cell(row=header_row, column=col).value
        )
        assert filled_cols == len(OUTPUT_COLUMNS)

    def test_meta_header(self, sample_df):
        data = build_excel(sample_df, "Sport AG", "Max", "EUR", 60)
        wb = load_workbook(io.BytesIO(data))
        ws = wb["Offerte"]
        assert ws.cell(row=1, column=2).value == "Sport AG"
        assert ws.cell(row=3, column=2).value == "Max"

    def test_total_row_exists(self, sample_df):
        data = build_excel(sample_df, "Test", "T", "CHF")
        wb = load_workbook(io.BytesIO(data))
        ws = wb["Offerte"]
        # TOTAL should be in row 8 (row 6 header + 1 data row + 1 total)
        assert ws.cell(row=8, column=1).value == "TOTAL"
