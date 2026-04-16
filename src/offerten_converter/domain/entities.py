"""Domain entities for the Offerten Converter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LineItem:
    """A single product line item extracted from a supplier quotation."""

    sku: Optional[str] = None
    ean: Optional[str] = None
    product_name: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    category: Optional[str] = None
    unit_price: Optional[float] = None
    currency: Optional[str] = None
    ordered_qty: Optional[int] = None
    min_qty: Optional[int] = None
    discount_pct: Optional[float] = None
    notes: Optional[str] = None
    extra_fields: dict = field(default_factory=dict)


@dataclass
class SupplierProfile:
    """Saved supplier profile – contains NO pricing data, NO contact info."""

    name: str
    typical_currency: str = "EUR"
    typical_discount: float = 0.0
    column_hints: str = ""


@dataclass
class QuotationSettings:
    """User-configurable settings for quotation generation."""

    default_margin: float = 40.0
    default_currency: str = "CHF"
    company_name: str = ""
    valid_days: int = 30
    rates: dict[str, float] = field(default_factory=dict)
