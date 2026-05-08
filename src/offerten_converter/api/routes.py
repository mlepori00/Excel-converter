"""API route handlers – thin wrappers over the existing application layer.

All business logic lives in application/ and infrastructure/.
These routes only marshal HTTP ↔ domain objects.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd
from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from offerten_converter.api import file_store
from offerten_converter.api.mappers import (
    build_export_preview,
    dataframe_to_product_rows,
    read_result_to_file_metadata,
)
from offerten_converter.application.calculate_prices import enrich_dataframe
from offerten_converter.application.export_quotation import export_to_excel
from offerten_converter.application.extract_products import extract_line_items
from offerten_converter.application.manage_profiles import profile_to_hints
from offerten_converter.application.sanitize_data import sanitize_dataframe
from offerten_converter.domain.pricing import DEFAULT_RATES
from offerten_converter.infrastructure import extraction_cache
from offerten_converter.infrastructure.ai_extractors import get_call_fn
from offerten_converter.infrastructure.excel_reader import (
    get_recommended_sheet_name,
    get_sheet_names,
    read_offer_file,
)
from offerten_converter.infrastructure.excel_writer import build_excel
from offerten_converter.infrastructure.file_profile_repo import FileProfileRepository

logger = logging.getLogger(__name__)
router = APIRouter()
_repo = FileProfileRepository()


def _row_to_dict(row: Any) -> dict:
    """Serialize a ProductRow dataclass to a plain dict."""
    import dataclasses
    d = dataclasses.asdict(row)
    # Convert enum values to their string form
    for k, v in d.items():
        if hasattr(v, "value"):
            d[k] = v.value
    return d


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ParseResponse(BaseModel):
    file_id: str
    filename: str
    sheets: list[str]
    selected_sheet: str | None
    row_count: int
    column_count: int
    detected_currency: str | None
    layout_type: str | None
    was_unpivoted: bool
    unpivot_info: str
    sanitizer_removed: int
    extraction_mode: str          # "local" | "cache" | "none"
    products: list[dict]          # ProductRow dicts
    api_cost_estimate_chf: float | None


class ExtractRequest(BaseModel):
    file_id: str
    sheet_name: str | None = None
    profile_name: str | None = None
    force_api: bool = False


class ExtractResponse(BaseModel):
    mode: str                     # "api" | "cache"
    products: list[dict]
    input_tokens: int
    output_tokens: int


class ExportRowIn(BaseModel):
    sku: str | None = None
    ean: str | None = None
    product_name: str | None = None
    size: str | None = None
    color: str | None = None
    category: str | None = None
    unit_price: float | None = None
    currency: str | None = None
    discount_pct: float | None = None
    notes: str | None = None
    availability_status: str | None = None
    min_qty: float | None = None
    available_qty: float | None = None
    ordered_qty: float | None = None
    vk_manual: float | None = None
    margin_pct: float = 40.0
    market_price: float | None = None


class ExportRequest(BaseModel):
    file_id: str
    supplier_name: str
    created_by: str = "AMP Sport GmbH"
    target_currency: str = "CHF"
    valid_days: int = 30
    default_margin_pct: float = 40.0
    rates: dict[str, float] | None = None
    rows: list[ExportRowIn]


class ProfileIn(BaseModel):
    typical_currency: str = "EUR"
    typical_discount: float = 0.0
    notes: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_file(file_bytes: bytes, filename: str, sheet_name: str | None) -> Any:
    """Read, select sheet, return ReadResult."""
    sheets = get_sheet_names(file_bytes, filename)
    if sheet_name and sheet_name not in sheets:
        raise HTTPException(400, f"Sheet '{sheet_name}' nicht gefunden. Verfügbar: {sheets}")
    chosen = sheet_name or get_recommended_sheet_name(file_bytes, filename) or (sheets[0] if sheets else None)
    return read_offer_file(file_bytes, filename, chosen), sheets, chosen


def _try_local_or_cache(
    file_bytes: bytes, result: Any, force: bool = False
) -> tuple[pd.DataFrame | None, str]:
    """Return (df, mode) from cache or local extraction, else (None, 'none')."""
    source_sheet = result.metadata_hints.get("source_sheet")
    if not force:
        for key in [
            extraction_cache.cache_key(file_bytes, source_sheet),
            extraction_cache.file_hash(file_bytes),
        ]:
            cached = extraction_cache.load(key)
            if cached is not None and not cached.empty:
                return _enforce_import_truth(cached, result.df), "cache"

    local = _build_local_extraction(result)
    if local is not None:
        local = _enforce_import_truth(local, result.df)
        extraction_cache.save(extraction_cache.cache_key(file_bytes, source_sheet), local)
        extraction_cache.save(extraction_cache.file_hash(file_bytes), local)
        return local, "local"

    return None, "none"


_LOCAL_COLS = [
    "sku", "ean", "product_name", "size", "color", "category",
    "unit_price", "currency", "ordered_qty", "available_qty",
    "availability_status", "min_qty", "discount_pct", "notes", "extra_fields",
]


def _has_values(series: pd.Series) -> bool:
    vals = series.dropna().astype(str).str.strip()
    return not vals[~vals.str.lower().isin(["", "nan", "none"])].empty


def _build_local_extraction(result: Any) -> pd.DataFrame | None:
    src = result.df.copy().reset_index(drop=True)
    if src.empty:
        return None
    has_identity = any(
        col in src.columns and _has_values(src[col])
        for col in ("product_name", "sku", "ean")
    )
    has_price = "unit_price" in src.columns and _has_values(src["unit_price"])
    has_variant = any(
        col in src.columns and _has_values(src[col])
        for col in ("size", "color", "available_qty")
    )
    if not (has_identity and has_price and has_variant):
        return None

    df = pd.DataFrame(index=src.index)
    for col in _LOCAL_COLS:
        if col == "extra_fields":
            df[col] = [{} for _ in range(len(src))]
        elif col in src.columns:
            df[col] = src[col].values
        else:
            df[col] = None
    df["ordered_qty"] = None

    id_cols = [c for c in ("product_name", "sku", "ean") if c in df.columns]
    if id_cols:
        identity = df[id_cols].fillna("").astype(str).agg("".join, axis=1).str.strip()
        df = df[identity != ""]
    return df.reset_index(drop=True) if not df.empty else None


def _enforce_import_truth(extracted: pd.DataFrame, import_df: pd.DataFrame) -> pd.DataFrame:
    df = extracted.copy().reset_index(drop=True)
    src = import_df.reset_index(drop=True)
    df["ordered_qty"] = None
    if len(src) != len(df):
        return df
    for col in ("sku", "ean", "product_name", "size", "color", "category",
                "available_qty", "unit_price", "currency", "discount_pct"):
        if col in src.columns and _has_values(src[col]):
            df[col] = src[col].values
    return df


def _api_cost_estimate(text: str) -> float:
    from offerten_converter.application.extract_products import (
        SYSTEM_PROMPT,
        _split_table_into_chunks,
    )
    chars_per_token = 4
    n_chunks = len(_split_table_into_chunks(text))
    system_tok = len(SYSTEM_PROMPT) // chars_per_token
    content_tok = len(text) // chars_per_token
    chunk_tok = content_tok // max(n_chunks, 1)
    total_in = (system_tok + chunk_tok) * n_chunks
    lines = [l for l in text.splitlines()[1:] if l.strip()]
    sample = lines[:20]
    avg_chars = sum(len(l) for l in sample) / max(len(sample), 1)
    total_out = int(len(lines) * avg_chars * 3.0 / chars_per_token)
    cost_usd = total_in / 1_000_000 * 15.0 + total_out / 1_000_000 * 75.0
    return round(cost_usd * 0.89, 4)


# ---------------------------------------------------------------------------
# Offer endpoints
# ---------------------------------------------------------------------------

@router.post("/offer/parse", response_model=ParseResponse)
async def parse_offer(
    file: UploadFile,
    sheet_name: str | None = Form(default=None),
    force_reparse: bool = Form(default=False),
) -> ParseResponse:
    """
    Upload a supplier Excel/CSV file.
    Returns file metadata, auto-extracted products (local or cache), and a file_id
    to reference this file in subsequent /extract and /export calls.
    """
    file_bytes = await file.read()
    filename = file.filename or "upload.xlsx"

    try:
        result, sheets, chosen = _parse_file(file_bytes, filename, sheet_name)
    except (ValueError, HTTPException) as exc:
        status = exc.status_code if isinstance(exc, HTTPException) else 400
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        raise HTTPException(status, detail) from exc
    file_id = file_store.put(file_bytes, filename)

    df_raw = result.df
    df_clean, sanitize_log = sanitize_dataframe(df_raw)
    removed = sum(1 for e in sanitize_log if e.startswith("Spalte"))

    products_df, mode = _try_local_or_cache(file_bytes, result, force=force_reparse)

    products: list[dict] = []
    if products_df is not None:
        products = [_row_to_dict(row) for row in dataframe_to_product_rows(products_df)]

    cost: float | None = None
    if mode == "none":
        sanitized_text = df_clean.to_string(index=False)
        cost = _api_cost_estimate(sanitized_text)

    hints = result.metadata_hints
    return ParseResponse(
        file_id=file_id,
        filename=filename,
        sheets=sheets,
        selected_sheet=chosen,
        row_count=len(df_raw),
        column_count=len(df_raw.columns),
        detected_currency=hints.get("detected_currency"),
        layout_type=hints.get("layout_type"),
        was_unpivoted=bool(result.was_unpivoted),
        unpivot_info=str(getattr(result, "unpivot_info", "") or ""),
        sanitizer_removed=removed,
        extraction_mode=mode,
        products=products,
        api_cost_estimate_chf=cost,
    )


@router.post("/offer/extract", response_model=ExtractResponse)
async def extract_products(body: ExtractRequest) -> ExtractResponse:
    """
    Run AI extraction on a previously uploaded file.
    Requires ANTHROPIC_API_KEY in environment.
    """
    entry = file_store.get(body.file_id)
    if entry is None:
        raise HTTPException(404, "Datei nicht gefunden oder abgelaufen. Bitte erneut hochladen.")

    file_bytes, filename = entry
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(500, "ANTHROPIC_API_KEY nicht gesetzt.")

    result, _, _ = _parse_file(file_bytes, filename, body.sheet_name)
    df_raw = result.df
    df_clean, _ = sanitize_dataframe(df_raw)
    sanitized_text = df_clean.to_string(index=False)

    hint_parts: list[str] = []
    if body.profile_name:
        profile = _repo.load(body.profile_name)
        if profile:
            hint_parts.append(profile_to_hints(profile))
    if result.metadata_hints.get("layout_type"):
        hint_parts.append(f"Detected offer layout: {result.metadata_hints['layout_type']}.")
    if result.was_unpivoted:
        hint_parts.append(
            "Data was unpivoted: '_size_from_col' = size, "
            "'_qty_from_col' = available_qty. ordered_qty must remain null."
        )
    if result.metadata_hints.get("detected_currency"):
        hint_parts.append(f"Detected currency: {result.metadata_hints['detected_currency']}")

    hints_str = " | ".join(hint_parts)

    try:
        items, usage = extract_line_items(
            sanitized_text, hints_str, api_key, call_fn=get_call_fn(api_key)
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(502, f"AI-Extraktion fehlgeschlagen: {exc}") from exc

    df_extracted = pd.DataFrame(items)
    df_extracted = _enforce_import_truth(df_extracted, result.df)

    source_sheet = result.metadata_hints.get("source_sheet")
    extraction_cache.save(extraction_cache.cache_key(file_bytes, source_sheet), df_extracted)
    extraction_cache.save(extraction_cache.file_hash(file_bytes), df_extracted)

    products = [_row_to_dict(row) for row in dataframe_to_product_rows(df_extracted)]
    return ExtractResponse(
        mode="api",
        products=products,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
    )


@router.post("/offer/export")
async def export_offer(body: ExportRequest) -> Response:
    """
    Apply per-row pricing and generate the AMP reseller Excel.
    Returns the .xlsx file as a binary download.
    """
    if not body.rows:
        raise HTTPException(400, "Keine Positionen übergeben.")
    if not body.supplier_name.strip():
        raise HTTPException(400, "Lieferantenname fehlt.")

    rates = body.rates or dict(DEFAULT_RATES)

    enriched_rows: list[pd.DataFrame] = []
    for row in body.rows:
        row_dict = row.model_dump(exclude={"vk_manual", "margin_pct"})
        row_df = pd.DataFrame([row_dict])

        enriched = enrich_dataframe(row_df, row.margin_pct, body.target_currency, rates)

        if row.vk_manual is not None and row.vk_manual > 0:
            enriched["vk_target"] = float(row.vk_manual)

        enriched_rows.append(enriched)

    enriched_df = pd.concat(enriched_rows, ignore_index=True)

    try:
        excel_bytes = export_to_excel(
            enriched_df,
            body.supplier_name,
            body.created_by,
            body.target_currency,
            body.valid_days,
            build_fn=build_excel,
        )
    except Exception as exc:
        logger.exception("Export fehlgeschlagen")
        raise HTTPException(500, f"Export-Fehler: {exc}") from exc

    from datetime import date
    filename = f"Offerte_{body.supplier_name.replace(' ', '_')}_{date.today():%Y%m%d}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Market price endpoints
# ---------------------------------------------------------------------------

class MarketPriceRequest(BaseModel):
    eans: list[str]


class MarketPriceResponse(BaseModel):
    prices: dict[str, float]   # ean -> lowest price found
    found: int
    total: int


@router.post("/offer/market-prices/stream")
async def stream_market_prices(body: MarketPriceRequest):
    """
    SSE endpoint: streams one JSON event per EAN as it is scraped.
    Event shape: {"ean": str, "price": float|null, "done": int, "total": int, "finished": bool}
    """
    import asyncio
    import json

    from fastapi.responses import StreamingResponse

    try:
        from offerten_converter.infrastructure.market_price_scraper import ToppreiseScraper
    except ImportError as exc:
        raise HTTPException(501, "Marktpreis-Scraper nicht verfügbar.") from exc

    unique_eans = list(dict.fromkeys(e.strip() for e in body.eans if e.strip()))
    if not unique_eans:
        raise HTTPException(400, "Keine EANs übergeben.")

    scraper = ToppreiseScraper()
    loop = asyncio.get_event_loop()
    total = len(unique_eans)
    results: list[tuple[str, float | None]] = []
    sem = asyncio.Semaphore(3)

    async def _fetch(ean: str) -> None:
        async with sem:
            price = await loop.run_in_executor(None, scraper.fetch_price, ean)
            results.append((ean, price))
            await asyncio.sleep(0.8)

    async def _generate():
        tasks = [asyncio.create_task(_fetch(ean)) for ean in unique_eans]
        order = {ean: i for i, ean in enumerate(unique_eans)}
        pending = set(unique_eans)
        reported = 0
        while pending:
            await asyncio.sleep(0.15)
            ready = [(ean, price) for ean, price in results if ean in pending]
            ready.sort(key=lambda x: order[x[0]])
            for ean, price in ready:
                pending.discard(ean)
                reported += 1
                event = {
                    "ean": ean,
                    "price": price,
                    "done": reported,
                    "total": total,
                    "finished": reported == total,
                }
                yield f"data: {json.dumps(event)}\n\n"
        await asyncio.gather(*tasks, return_exceptions=True)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Profile endpoints
# ---------------------------------------------------------------------------

@router.get("/profiles")
def list_profiles() -> list[str]:
    return _repo.list_profiles()


@router.get("/profiles/{name}")
def get_profile(name: str) -> dict:
    profile = _repo.load(name)
    if profile is None:
        raise HTTPException(404, f"Profil '{name}' nicht gefunden.")
    return profile


@router.post("/profiles/{name}", status_code=201)
def save_profile(name: str, body: ProfileIn) -> dict:
    _repo.save(name, body.typical_currency, body.typical_discount, body.notes)
    return {"saved": name}


@router.delete("/profiles/{name}", status_code=204)
def delete_profile(name: str) -> None:
    profiles = _repo.list_profiles()
    if name not in profiles:
        raise HTTPException(404, f"Profil '{name}' nicht gefunden.")
    _repo.delete(name)
