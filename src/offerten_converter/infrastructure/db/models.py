"""SQLAlchemy ORM models.

Models are imported by init_db() so they register on Base.metadata before
create_all() runs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from offerten_converter.infrastructure.db.base import Base


class UserModel(Base):
    """An application user (one row per person who can log in)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OfferModel(Base):
    """An archived offer: metadata + both files (original supplier + generated)."""

    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Filing taxonomy: year > brand > supplier.
    jahr: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    marke: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    lieferant: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="erstellt", server_default="erstellt", index=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_by_name: Mapped[str] = mapped_column(String(255), nullable=False)

    target_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    default_margin: Mapped[float] = mapped_column(Float, nullable=False)

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # Blobs are deferred: list/detail queries don't load them; only file downloads do.
    original_file: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    generated_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    generated_file: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    line_items: Mapped[list["OfferLineItemModel"]] = relationship(
        back_populates="offer",
        cascade="all, delete-orphan",
        order_by="OfferLineItemModel.position",
    )


class OfferLineItemModel(Base):
    """A single stored position of an archived offer."""

    __tablename__ = "offer_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    offer_id: Mapped[int] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    sku: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    ean: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    product_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    size: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    unit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    ordered_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    available_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    discount_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vk_unit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vk_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    margin_actual: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    extra_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Origin cell in the original supplier file – filled in phase 3 (round-trip).
    provenance: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    offer: Mapped["OfferModel"] = relationship(back_populates="line_items")
