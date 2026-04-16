"""Unit tests for data sanitization."""

import pandas as pd

from offerten_converter.application.sanitize_data import (
    _cell_contains_pii,
    _col_is_sensitive,
    sanitize_dataframe,
)


class TestColIsSensitive:
    def test_email_column(self):
        assert _col_is_sensitive("Email") is True
        assert _col_is_sensitive("E-Mail") is True

    def test_supplier_column(self):
        assert _col_is_sensitive("Lieferant") is True
        assert _col_is_sensitive("lieferantenname") is True

    def test_customer_column(self):
        assert _col_is_sensitive("Kundenname") is True
        assert _col_is_sensitive("Empfänger") is True

    def test_product_name_not_sensitive(self):
        assert _col_is_sensitive("product_name") is False
        assert _col_is_sensitive("Bezeichnung") is False

    def test_unnamed_columns_not_sensitive(self):
        assert _col_is_sensitive("Unnamed: 0") is False
        assert _col_is_sensitive("Unnamed: 7") is False

    def test_phone_column(self):
        assert _col_is_sensitive("Telefon") is True
        assert _col_is_sensitive("Phone Number") is True


class TestCellContainsPii:
    def test_email_detected(self):
        assert _cell_contains_pii("Contact: test@example.com") is True

    def test_iban_detected(self):
        assert _cell_contains_pii("CH9300762011623852957") is True

    def test_phone_detected(self):
        assert _cell_contains_pii("+41 79 123 45 67") is True

    def test_normal_text_clean(self):
        assert _cell_contains_pii("BLACKROLL STANDARD schwarz") is False

    def test_ean_not_flagged(self):
        assert _cell_contains_pii("4260346270001") is False

    def test_sku_not_flagged(self):
        assert _cell_contains_pii("CCM-TASV-SR-75") is False


class TestSanitizeDataframe:
    def test_removes_email_column(self):
        df = pd.DataFrame({"product": ["A"], "Email": ["test@x.com"]})
        sanitized, log = sanitize_dataframe(df)
        assert "Email" not in sanitized.columns
        assert any("Email" in entry for entry in log)

    def test_scrubs_email_from_cell(self):
        df = pd.DataFrame({"notes": ["Contact info@example.com for orders"]})
        sanitized, log = sanitize_dataframe(df)
        assert "[REDACTED]" in sanitized.iloc[0]["notes"]
        assert any("email" in entry for entry in log)

    def test_preserves_product_data(self):
        df = pd.DataFrame({
            "product_name": ["BLACKROLL STANDARD"],
            "sku": ["BR-001"],
            "ean": ["4260346270001"],
            "unit_price": [24.90],
        })
        sanitized, log = sanitize_dataframe(df)
        assert len(sanitized.columns) == 4
        assert sanitized.iloc[0]["product_name"] == "BLACKROLL STANDARD"
        assert log == []
