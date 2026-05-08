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
