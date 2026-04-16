"""Unit tests for domain entities."""

from offerten_converter.domain.entities import LineItem, QuotationSettings, SupplierProfile


def test_line_item_defaults():
    item = LineItem()
    assert item.sku is None
    assert item.unit_price is None
    assert item.ordered_qty is None


def test_line_item_with_values():
    item = LineItem(
        sku="BR-STD-001",
        product_name="BLACKROLL STANDARD",
        unit_price=24.90,
        currency="EUR",
        ordered_qty=10,
        discount_pct=5.0,
    )
    assert item.sku == "BR-STD-001"
    assert item.unit_price == 24.90
    assert item.ordered_qty == 10


def test_supplier_profile_defaults():
    profile = SupplierProfile(name="Test")
    assert profile.typical_currency == "EUR"
    assert profile.typical_discount == 0.0
    assert profile.column_hints == ""


def test_quotation_settings_defaults():
    settings = QuotationSettings()
    assert settings.default_margin == 40.0
    assert settings.default_currency == "CHF"
    assert settings.valid_days == 30
    assert settings.rates == {}
