"""Integration tests for supplier offer Excel import normalization."""

from __future__ import annotations

import io

import pandas as pd

from offerten_converter.infrastructure.excel_reader import read_offer_file


def test_reads_prices_from_rrp_in_zusatzinfos_when_ek_is_blank():
    buf = io.BytesIO()
    source = pd.DataFrame({
        "Pos": ["1", "2", "TOTAL", "AMP Sport GmbH · www.ampsport.ch"],
        "Bezeichnung": [
            "Air Jordan 1 Low",
            "Nike Air Max 95 OG",
            None,
            "AMP Sport GmbH · www.ampsport.ch",
        ],
        "SKU": [
            "DC0774-105",
            "HJ5996-002",
            None,
            "AMP Sport GmbH · www.ampsport.ch",
        ],
        "Grösse": ["5", "5.5", None, "AMP Sport GmbH · www.ampsport.ch"],
        "Max. verfügbar": [25, 42, None, "AMP Sport GmbH · www.ampsport.ch"],
        "EK/Stk": [None, None, None, "AMP Sport GmbH · www.ampsport.ch"],
        "Zusatzinfos": [
            "gender: WOMENS | rrp: 129,99 € | total: 1438",
            "gender: WOMENS | rrp: 189,99 € | total: 2481+",
            None,
            "AMP Sport GmbH · www.ampsport.ch",
        ],
        "Währung": ["EUR", "EUR", None, "AMP Sport GmbH · www.ampsport.ch"],
    })
    source.to_excel(buf, index=False)

    result = read_offer_file(buf.getvalue(), "nike_offer.xlsx")

    assert result.df["unit_price"].tolist() == ["129.99", "189.99"]
    assert result.df["available_qty"].astype(str).tolist() == ["25", "42"]
    assert len(result.df) == 2
    assert result.metadata_hints["column_mapping"]["unit_price"] == "EK/Stk + Zusatzinfos (rrp)"
    assert result.metadata_hints["column_mapping"]["available_qty"] == "Max. verfügbar"
    assert result.metadata_hints["detected_currency"] == "EUR"


def test_empty_trade_price_falls_back_to_populated_rrp():
    """A well-named but empty price column ('Deal') must not block a populated 'RRP'."""
    buf = io.BytesIO()
    pd.DataFrame({
        "Styles": ["DC0774-105", "HJ5996-002"],
        "Description": ["Air Jordan 1 Low", "Nike Air Max 95 OG"],
        "Color description": ["WOLF GREY", "BLACK"],
        "Grösse": ["42", "43"],
        "Deal": [None, None],            # named like a price, but empty
        "RRP": ["129.99", "189.99"],     # the actual populated price
        "Total": [25, 42],
    }).to_excel(buf, index=False)

    result = read_offer_file(buf.getvalue(), "nike_availability.xlsx")

    assert result.df["unit_price"].tolist() == ["129.99", "189.99"]
    assert result.metadata_hints["column_mapping"]["unit_price"] == "RRP (rrp/retail)"


def test_populated_trade_price_wins_over_rrp():
    """When the trade price has values, it is preferred over retail/RRP."""
    buf = io.BytesIO()
    pd.DataFrame({
        "Styles": ["A-1", "A-2"],
        "Description": ["Shoe One", "Shoe Two"],
        "Grösse": ["42", "43"],
        "Deal": ["59.90", "69.90"],      # trade price, populated
        "RRP": ["129.99", "189.99"],
        "Total": [25, 42],
    }).to_excel(buf, index=False)

    result = read_offer_file(buf.getvalue(), "supplier.xlsx")

    assert result.df["unit_price"].tolist() == ["59.90", "69.90"]
    assert result.metadata_hints["column_mapping"]["unit_price"] == "Deal"


def test_empty_size_grid_keeps_flat_rows_instead_of_deleting_them():
    """A blank size grid (unfilled order form) must not be unpivoted to zero rows.

    Numeric size headers (38-41) with no quantities used to trigger an unpivot
    that filtered every row away, destroying the real flat data (price + identity)
    for all downstream paths. The reader must keep the rows and read flat instead.
    """
    buf = io.BytesIO()
    pd.DataFrame({
        "REF": ["A-1", "A-2", "A-3", "A-4"],
        "Description": ["Shoe One", "Shoe Two", "Shoe Three", "Shoe Four"],
        "Color": ["GREY", "BLACK", "WHITE", "BLUE"],
        "EAN": ["1234567890123", "1234567890124", "1234567890125", "1234567890126"],
        "COSTE": ["6.36", "5.16", "7.20", "8.10"],   # real purchase price (Spanish header)
        "38": [None, None, None, None],              # empty size grid (order-form template)
        "39": [None, None, None, None],
        "40": [None, None, None, None],
        "41": [None, None, None, None],
    }).to_excel(buf, index=False)

    result = read_offer_file(buf.getvalue(), "birkenstock_order_form.xlsx")

    assert len(result.df) == 4
    assert result.was_unpivoted is False
    assert result.metadata_hints["layout_type"] == "flat_variant_rows"
    assert result.df["unit_price"].tolist() == ["6.36", "5.16", "7.20", "8.10"]


def test_raw_fallback_when_all_rows_removed_as_footer():
    """Safety net: if all heuristics empty the frame, return the raw snapshot.

    _drop_non_product_rows filters rows whose identity columns contain footer
    terms like "www.". When that removes every row, read_offer_file must not
    return an empty DataFrame — it falls back to the minimally-processed sheet.
    """
    buf = io.BytesIO()
    pd.DataFrame({
        "SKU": ["www.supplier.com", "www.supplier.com"],
        "Price EUR": ["59.90", "79.90"],
        "Description": ["Red Shirt", "Blue Pants"],
    }).to_excel(buf, index=False)

    result = read_offer_file(buf.getvalue(), "offer.xlsx")

    assert not result.df.empty
    assert result.metadata_hints.get("layout_type") == "raw_fallback"
    assert result.metadata_hints.get("was_raw_fallback") is True
    assert len(result.df) == 2
    assert result.was_unpivoted is False


def test_filled_size_grid_still_unpivots():
    """A populated size grid must still expand into one row per available size."""
    buf = io.BytesIO()
    pd.DataFrame({
        "REF": ["A-1", "A-2"],
        "Description": ["Shoe One", "Shoe Two"],
        "38": ["5", "0"],
        "39": ["0", "3"],
        "40": ["2", "0"],
    }).to_excel(buf, index=False)

    result = read_offer_file(buf.getvalue(), "supplier_grid.xlsx")

    assert result.was_unpivoted is True
    assert result.metadata_hints["layout_type"] == "size_matrix_columns"
    # A-1: sizes 38,40 (qty>0); A-2: size 39 → 3 variant rows total
    assert len(result.df) == 3
