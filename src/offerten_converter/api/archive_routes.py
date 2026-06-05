"""Archive API: list, detail, downloads, status, and tree navigation.

Mounted under /api with the get_current_user guard (see server.py).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from offerten_converter.application.ports import SpreadsheetPreviewRenderer
from offerten_converter.domain.entities import Offer, OfferStatus
from offerten_converter.infrastructure.db.engine import get_db
from offerten_converter.infrastructure.excel_html_renderer import ExcelHtmlRenderer
from offerten_converter.infrastructure.sql_offer_repo import SqlOfferRepository

router = APIRouter()

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_renderer = ExcelHtmlRenderer()


def _repo(db: Session = Depends(get_db)) -> SqlOfferRepository:
    return SqlOfferRepository(db)


def get_renderer() -> SpreadsheetPreviewRenderer:
    return _renderer


# --- schemas --------------------------------------------------------------

class OfferSummaryOut(BaseModel):
    id: int
    jahr: int
    marke: str
    lieferant: str
    status: str
    created_by_name: str
    created_at: datetime | None
    title: str | None
    original_filename: str
    generated_filename: str


class OfferLineOut(BaseModel):
    position: int
    sku: str | None
    ean: str | None
    product_name: str | None
    size: str | None
    color: str | None
    category: str | None
    unit_price: float | None
    currency: str | None
    ordered_qty: int | None
    available_qty: int | None
    discount_pct: float | None
    vk_unit: float | None
    vk_total: float | None
    margin_actual: float | None
    notes: str | None


class OfferDetailOut(OfferSummaryOut):
    line_items: list[OfferLineOut]


class StatusUpdate(BaseModel):
    status: str


class TreeSupplier(BaseModel):
    lieferant: str
    count: int


class TreeBrand(BaseModel):
    marke: str
    count: int
    lieferanten: list[TreeSupplier]


class TreeYear(BaseModel):
    jahr: int
    count: int
    marken: list[TreeBrand]


# --- mapping --------------------------------------------------------------

def _summary(o: Offer) -> OfferSummaryOut:
    assert o.id is not None
    return OfferSummaryOut(
        id=o.id,
        jahr=o.jahr,
        marke=o.marke,
        lieferant=o.lieferant,
        status=o.status.value,
        created_by_name=o.created_by_name,
        created_at=o.created_at,
        title=o.title,
        original_filename=o.original_filename,
        generated_filename=o.generated_filename,
    )


def _detail(o: Offer) -> OfferDetailOut:
    base = _summary(o).model_dump()
    return OfferDetailOut(
        **base,
        line_items=[
            OfferLineOut(
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
            )
            for li in o.line_items
        ],
    )


def _parse_status(value: str | None) -> OfferStatus | None:
    if not value:
        return None
    try:
        return OfferStatus(value)
    except ValueError as exc:
        raise HTTPException(400, f"Ungültiger Status: {value}") from exc


# --- endpoints ------------------------------------------------------------

@router.get("/offers", response_model=list[OfferSummaryOut])
def list_offers(
    jahr: int | None = None,
    marke: str | None = None,
    lieferant: str | None = None,
    status: str | None = None,
    q: str | None = None,
    repo: SqlOfferRepository = Depends(_repo),
) -> list[OfferSummaryOut]:
    offers = repo.list(
        jahr=jahr,
        marke=marke,
        lieferant=lieferant,
        status=_parse_status(status),
        query=q,
    )
    return [_summary(o) for o in offers]


@router.get("/offers/tree", response_model=list[TreeYear])
def offers_tree(repo: SqlOfferRepository = Depends(_repo)) -> list[TreeYear]:
    """Year -> brand -> supplier counts for the archive navigation."""
    offers = repo.list()
    # year -> marke -> lieferant -> count
    tree: dict[int, dict[str, dict[str, int]]] = {}
    for o in offers:
        tree.setdefault(o.jahr, {}).setdefault(o.marke, {})
        tree[o.jahr][o.marke][o.lieferant] = tree[o.jahr][o.marke].get(o.lieferant, 0) + 1

    result: list[TreeYear] = []
    for jahr in sorted(tree, reverse=True):
        marken: list[TreeBrand] = []
        for marke in sorted(tree[jahr]):
            suppliers = tree[jahr][marke]
            lieferanten = [
                TreeSupplier(lieferant=lf, count=suppliers[lf]) for lf in sorted(suppliers)
            ]
            marken.append(
                TreeBrand(marke=marke, count=sum(suppliers.values()), lieferanten=lieferanten)
            )
        result.append(
            TreeYear(jahr=jahr, count=sum(b.count for b in marken), marken=marken)
        )
    return result


@router.get("/offers/{offer_id}", response_model=OfferDetailOut)
def get_offer(offer_id: int, repo: SqlOfferRepository = Depends(_repo)) -> OfferDetailOut:
    offer = repo.get(offer_id)
    if offer is None:
        raise HTTPException(404, "Offerte nicht gefunden")
    return _detail(offer)


@router.patch("/offers/{offer_id}/status", response_model=OfferSummaryOut)
def set_offer_status(
    offer_id: int, body: StatusUpdate, repo: SqlOfferRepository = Depends(_repo)
) -> OfferSummaryOut:
    status = _parse_status(body.status)
    if status is None:
        raise HTTPException(400, "Status fehlt")
    updated = repo.update_status(offer_id, status)
    if updated is None:
        raise HTTPException(404, "Offerte nicht gefunden")
    return _summary(updated)


@router.get("/offers/{offer_id}/original")
def download_original(offer_id: int, repo: SqlOfferRepository = Depends(_repo)) -> Response:
    result = repo.get_original_file(offer_id)
    if result is None:
        raise HTTPException(404, "Offerte nicht gefunden")
    data, filename = result
    if not data:
        raise HTTPException(404, "Keine Original-Datei vorhanden")
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename or "original.xlsx"}"'},
    )


@router.get("/offers/{offer_id}/generated")
def download_generated(offer_id: int, repo: SqlOfferRepository = Depends(_repo)) -> Response:
    result = repo.get_generated_file(offer_id)
    if result is None:
        raise HTTPException(404, "Offerte nicht gefunden")
    data, filename = result
    return Response(
        content=data,
        media_type=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename or "offerte.xlsx"}"'},
    )


@router.get("/offers/{offer_id}/preview/{which}")
def preview_offer(
    offer_id: int,
    which: str,
    repo: SqlOfferRepository = Depends(_repo),
    renderer: SpreadsheetPreviewRenderer = Depends(get_renderer),
) -> Response:
    """Return an HTML rendering of the original or generated file for previewing."""
    if which not in ("original", "generated"):
        raise HTTPException(404, "Unbekannte Vorschau")

    src = repo.get_file(offer_id, which)
    if src is None:
        raise HTTPException(404, "Offerte nicht gefunden")
    data, filename = src
    if not data:
        raise HTTPException(404, "Keine Datei vorhanden")

    suffix = Path(filename or "").suffix or ".xlsx"
    try:
        html = renderer.to_html(data, src_suffix=suffix)
    except Exception as exc:  # rendering failure -> surface as 500
        raise HTTPException(500, "Vorschau konnte nicht erzeugt werden") from exc

    return Response(content=html, media_type="text/html; charset=utf-8")
