"""Domain entities for the Offerten Converter."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
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
    available_qty: Optional[int] = None
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
class User:
    """An application user. `password_hash` is a credential detail and must
    never be serialised into an API response."""

    email: str
    name: str
    password_hash: str
    id: Optional[int] = None
    is_active: bool = True
    must_change_password: bool = False
    created_at: Optional[datetime] = None


class OfferStatus(str, Enum):
    """Lifecycle of an archived offer."""

    CREATED = "erstellt"
    SENT = "versendet"
    ORDER_RECEIVED = "bestellung_erhalten"
    COMPLETED = "abgeschlossen"


@dataclass
class OfferLine:
    """A single stored position of an archived offer (priced)."""

    position: int = 0
    sku: Optional[str] = None
    ean: Optional[str] = None
    product_name: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    category: Optional[str] = None
    unit_price: Optional[float] = None
    currency: Optional[str] = None
    ordered_qty: Optional[int] = None
    available_qty: Optional[int] = None
    discount_pct: Optional[float] = None
    vk_unit: Optional[float] = None
    vk_total: Optional[float] = None
    margin_actual: Optional[float] = None
    notes: Optional[str] = None
    extra_fields: dict = field(default_factory=dict)
    # Cell origin in the original supplier file – filled in phase 3 (round-trip).
    provenance: Optional[dict] = None


@dataclass
class Offer:
    """An archived offer. Metadata + line items; file blobs live in the repo."""

    jahr: int
    marke: str
    lieferant: str
    created_by_name: str
    target_currency: str
    default_margin: float
    original_filename: str
    generated_filename: str
    status: OfferStatus = OfferStatus.CREATED
    created_by_user_id: Optional[int] = None
    title: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    line_items: list[OfferLine] = field(default_factory=list)


@dataclass
class QuotationSettings:
    """User-configurable settings for quotation generation."""

    default_margin: float = 40.0
    default_currency: str = "CHF"
    company_name: str = ""
    valid_days: int = 30
    rates: dict[str, float] = field(default_factory=dict)
