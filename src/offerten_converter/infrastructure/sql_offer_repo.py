"""SQLAlchemy-backed implementation of the OfferRepository port."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from offerten_converter.application.ports import OfferRepository
from offerten_converter.domain.entities import Offer, OfferLine, OfferStatus
from offerten_converter.infrastructure.db.models import OfferLineItemModel, OfferModel


def _line_to_domain(li: OfferLineItemModel) -> OfferLine:
    return OfferLine(
        position=li.position,
        sku=li.sku,
        ean=li.ean,
        product_name=li.product_name,
        size=li.size,
        color=li.color,
        category=li.category,
        unit_price=li.unit_price,
        currency=li.currency,
        ordered_qty=li.ordered_qty,
        available_qty=li.available_qty,
        discount_pct=li.discount_pct,
        vk_unit=li.vk_unit,
        vk_total=li.vk_total,
        margin_actual=li.margin_actual,
        notes=li.notes,
        extra_fields=li.extra_fields or {},
        provenance=li.provenance,
    )


def _offer_to_domain(row: OfferModel, *, with_lines: bool = True) -> Offer:
    return Offer(
        id=row.id,
        jahr=row.jahr,
        marke=row.marke,
        lieferant=row.lieferant,
        status=OfferStatus(row.status),
        title=row.title,
        created_by_user_id=row.created_by_user_id,
        created_by_name=row.created_by_name,
        target_currency=row.target_currency,
        default_margin=row.default_margin,
        original_filename=row.original_filename,
        generated_filename=row.generated_filename,
        created_at=row.created_at,
        updated_at=row.updated_at,
        line_items=[_line_to_domain(li) for li in row.line_items] if with_lines else [],
    )


class SqlOfferRepository(OfferRepository):
    """Offer persistence using a SQLAlchemy session (one per request)."""

    def __init__(self, session: Session):
        self._s = session

    def create(self, offer: Offer, original_bytes: bytes, generated_bytes: bytes) -> Offer:
        row = OfferModel(
            jahr=offer.jahr,
            marke=offer.marke,
            lieferant=offer.lieferant,
            status=offer.status.value,
            title=offer.title,
            created_by_user_id=offer.created_by_user_id,
            created_by_name=offer.created_by_name,
            target_currency=offer.target_currency,
            default_margin=offer.default_margin,
            original_filename=offer.original_filename,
            original_file=original_bytes,
            generated_filename=offer.generated_filename,
            generated_file=generated_bytes,
        )
        for li in offer.line_items:
            row.line_items.append(
                OfferLineItemModel(
                    position=li.position,
                    sku=li.sku,
                    ean=li.ean,
                    product_name=li.product_name,
                    size=li.size,
                    color=li.color,
                    category=li.category,
                    unit_price=li.unit_price,
                    currency=li.currency,
                    ordered_qty=li.ordered_qty,
                    available_qty=li.available_qty,
                    discount_pct=li.discount_pct,
                    vk_unit=li.vk_unit,
                    vk_total=li.vk_total,
                    margin_actual=li.margin_actual,
                    notes=li.notes,
                    extra_fields=li.extra_fields or None,
                    provenance=li.provenance,
                )
            )
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return _offer_to_domain(row)

    def get(self, offer_id: int) -> Offer | None:
        row = self._s.get(OfferModel, offer_id)
        return _offer_to_domain(row) if row is not None else None

    def list(
        self,
        *,
        jahr: int | None = None,
        marke: str | None = None,
        lieferant: str | None = None,
        status: OfferStatus | None = None,
        query: str | None = None,
    ) -> list[Offer]:
        stmt = select(OfferModel)
        if jahr is not None:
            stmt = stmt.where(OfferModel.jahr == jahr)
        if marke:
            stmt = stmt.where(OfferModel.marke == marke)
        if lieferant:
            stmt = stmt.where(OfferModel.lieferant == lieferant)
        if status is not None:
            stmt = stmt.where(OfferModel.status == status.value)
        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(
                    OfferModel.marke.ilike(like),
                    OfferModel.lieferant.ilike(like),
                    OfferModel.title.ilike(like),
                )
            )
        stmt = stmt.order_by(OfferModel.created_at.desc(), OfferModel.id.desc())
        rows = self._s.scalars(stmt).all()
        return [_offer_to_domain(r, with_lines=False) for r in rows]

    def get_original_file(self, offer_id: int) -> tuple[bytes, str] | None:
        row = self._s.get(OfferModel, offer_id)
        if row is None:
            return None
        return row.original_file, row.original_filename

    def get_generated_file(self, offer_id: int) -> tuple[bytes, str] | None:
        row = self._s.get(OfferModel, offer_id)
        if row is None:
            return None
        return row.generated_file, row.generated_filename

    # which -> (source-file column, filename column)
    _FILE_COLUMNS = {
        "original": ("original_file", "original_filename"),
        "generated": ("generated_file", "generated_filename"),
    }

    def get_file(self, offer_id: int, which: str) -> tuple[bytes, str] | None:
        """Return (bytes, filename) of the original or generated file, or None."""
        file_col, name_col = self._FILE_COLUMNS[which]
        row = self._s.get(OfferModel, offer_id)
        if row is None:
            return None
        return getattr(row, file_col), getattr(row, name_col)

    def update_status(self, offer_id: int, status: OfferStatus) -> Offer | None:
        row = self._s.get(OfferModel, offer_id)
        if row is None:
            return None
        row.status = status.value
        self._s.commit()
        self._s.refresh(row)
        return _offer_to_domain(row)
