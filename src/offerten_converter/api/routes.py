"""API route handlers – thin wrappers over the existing application layer.

All business logic lives in application/ and infrastructure/.
These routes only marshal HTTP ↔ domain objects.
"""

from __future__ import annotations

import io
import logging
import os
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from offerten_converter.api import file_store
from offerten_converter.api.auth import get_current_user
from offerten_converter.api.mappers import (
    _to_float,
    _to_int,
    dataframe_to_product_rows,
)
from offerten_converter.application.calculate_prices import enrich_dataframe
from offerten_converter.application.export_quotation import export_to_excel
from offerten_converter.application.extract_products import extract_line_items
from offerten_converter.application.manage_profiles import profile_to_hints
from offerten_converter.application.sanitize_data import sanitize_dataframe
from offerten_converter.domain.entities import Offer, OfferLine, OfferStatus, User
from offerten_converter.domain.pricing import DEFAULT_RATES
from offerten_converter.infrastructure import extraction_cache
from offerten_converter.infrastructure.ai_extractors import get_call_fn
from offerten_converter.infrastructure.column_mapper import (
    CANONICAL_FIELDS,
    apply_mapping,
    estimate_cost_chf,
    map_columns,
)
from offerten_converter.infrastructure.db.engine import get_db
from offerten_converter.infrastructure.ecb_rates import fetch_ecb_rates
from offerten_converter.infrastructure.excel_reader import (
    get_recommended_sheet_name,
    get_sheet_names,
    read_offer_file,
)
from offerten_converter.infrastructure.excel_writer import build_excel
from offerten_converter.infrastructure.file_profile_repo import FileProfileRepository
from offerten_converter.infrastructure.sql_offer_repo import SqlOfferRepository

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
    map_columns_cost_estimate_chf: float | None
    extraction_diagnostics: str | None = None  # why mode=none; null otherwise


class MapColumnsRequest(BaseModel):
    file_id: str


class MapColumnsResponse(BaseModel):
    mapped_fields: dict[str, str]   # {canonical_field: original_column}
    columns_total: int
    columns_mapped: int
    unmapped_columns: list[str]     # original column names not assigned to any field
    products: list[dict]


class ColumnOptionsResponse(BaseModel):
    columns: list[dict]             # [{"name": str, "samples": list[str]}]
    current_mapping: dict[str, str] # {canonical_field: original_column} pre-fill
    fields: list[str]               # canonical field keys, in display order


class ColumnOptionsRequest(BaseModel):
    file_id: str
    # The mapping currently applied to the products on screen (e.g. from the AI
    # column mapper). Used to pre-fill the manual dialog so fields the heuristic
    # alone could not resolve are not silently dropped.
    prior_mapping: dict[str, str] = {}


class RemapRequest(BaseModel):
    file_id: str
    mapping: dict[str, str]         # {canonical_field: original_column}; "" = unset
    prior_mapping: dict[str, str] = {}  # currently-applied mapping to build upon


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
    margin_pct: float = 20.0
    market_price: float | None = None


class ExportRequest(BaseModel):
    file_id: str
    supplier_name: str
    marke: str = ""
    created_by: str = "AMP Sport GmbH"
    target_currency: str = "CHF"
    valid_days: int = 30
    default_margin_pct: float = 20.0
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
    chosen = (
        sheet_name
        or get_recommended_sheet_name(file_bytes, filename)
        or (sheets[0] if sheets else None)
    )
    result = read_offer_file(file_bytes, filename, chosen)
    return result, sheets, chosen


def _try_local_or_cache(
    file_bytes: bytes, result: Any, force: bool = False
) -> tuple[pd.DataFrame | None, str]:
    """Return (df, mode) from cache or local extraction, else (None, 'none')."""
    source_sheet = result.metadata_hints.get("source_sheet")
    if not force:
        for key in [
            extraction_cache.cache_key(file_bytes, source_sheet),
            extraction_cache.cache_key(file_bytes),
        ]:
            cached = extraction_cache.load(key)
            if cached is not None and not cached.empty:
                return _enforce_import_truth(cached, result.df), "cache"

    local = _build_local_extraction(result)
    if local is not None:
        local = _enforce_import_truth(local, result.df)
        extraction_cache.save(extraction_cache.cache_key(file_bytes, source_sheet), local)
        extraction_cache.save(extraction_cache.cache_key(file_bytes), local)
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


def _build_extraction_diagnostics(result: Any) -> str | None:
    """Human-readable explanation of why local extraction produced nothing."""
    if result.metadata_hints.get("was_raw_fallback"):
        return (
            "Dateistruktur konnte nicht erkannt werden – "
            "Spalten manuell zuordnen oder KI verwenden."
        )
    df = result.df
    if df.empty:
        return "Keine Zeilen im Sheet erkannt."
    has_identity = any(
        col in df.columns and _has_values(df[col])
        for col in ("product_name", "sku", "ean")
    )
    has_price = "unit_price" in df.columns and _has_values(df["unit_price"])
    has_variant = any(
        col in df.columns and _has_values(df[col])
        for col in ("size", "color", "available_qty")
    )
    issues = []
    if not has_price:
        issues.append("Kein Preisfeld erkannt")
    if not has_identity:
        issues.append("Keine Produkt-Identifier (SKU/EAN/Name)")
    if not has_variant:
        issues.append("Keine Varianten-Info (Grösse/Farbe/Menge)")
    return " · ".join(issues) if issues else None


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

    # Collect unmapped text columns with meaningful content into extra_fields.
    # "Unmapped" = not a canonical field and not an internal unpivot column.
    _internal = {"_size_from_col", "_qty_from_col"}
    extra_cols = [
        c for c in src.columns
        if c not in _LOCAL_COLS and c not in _internal and src[c].dtype == object
    ]
    extra_cols = [
        c for c in extra_cols
        if pd.notna(avg := src[c].dropna().astype(str).str.strip().str.len().mean()) and avg > 3
    ]

    df = pd.DataFrame(index=src.index)
    for col in _LOCAL_COLS:
        if col == "extra_fields":
            if extra_cols:
                def _build_extra(row: pd.Series) -> dict:
                    return {
                        str(c): str(row[c]).strip()
                        for c in extra_cols
                        if not (pd.isna(row[c]) or str(row[c]).strip() in ("", "nan", "None"))
                    }
                df[col] = [_build_extra(src.iloc[i]) for i in range(len(src))]
            else:
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


def _sample_values(series: Any, n: int = 3) -> list[str]:
    """Return up to *n* distinct non-empty sample values from a column."""
    vals = series.dropna().astype(str).str.strip()
    vals = vals[~vals.str.lower().isin(["", "nan", "none"])]
    seen: list[str] = []
    for v in vals.tolist():
        if v not in seen:
            seen.append(v)
        if len(seen) >= n:
            break
    return seen


def _raw_source(label: str) -> str:
    """Strip resolver annotations to recover the underlying column name.

    e.g. "RRP (rrp/retail)" -> "RRP"; "EK/Stk + Zusatzinfos (rrp)" -> "EK/Stk".
    """
    return str(label).split(" + ")[0].split(" (")[0].strip()


def _read_for_mapping(
    file_bytes: bytes,
    filename: str,
    prior: dict[str, str] | None = None,
) -> tuple[Any, list[str], dict[str, str]]:
    """Read a file and return (result, original_columns, current_mapping).

    original_columns = the real supplier headers (heuristic-added canonical columns
    excluded). current_mapping = {canonical: original_column} the heuristic resolved,
    limited to those pointing at a selectable original column (for UI pre-fill).

    *prior* is the mapping currently applied to the on-screen products (e.g. fields
    the AI column mapper resolved that the heuristic alone missed). It is merged on
    top of the heuristic result so the manual flow builds on what is already there
    instead of silently dropping AI-only mappings such as the SKU column.
    """
    result, _, _ = _parse_file(file_bytes, filename, None)
    heuristic_mapping = result.metadata_hints.get("column_mapping", {})
    heuristic_added = {
        canonical for canonical, original in heuristic_mapping.items()
        if canonical != original
    }
    original_cols = [
        str(c) for c in result.df.columns
        if not str(c).startswith("_") and str(c) not in heuristic_added
    ]
    current: dict[str, str] = {}
    for canonical, label in {**heuristic_mapping, **(prior or {})}.items():
        raw = _raw_source(label)
        if raw in original_cols:
            current[canonical] = raw
    return result, original_cols, current


def _map_columns_cost(result: Any) -> float:
    """Estimate CHF cost of the Haiku column-mapper for this file's original columns."""
    if result.was_raw_fallback:
        return 0.0
    heuristic_mapping = result.metadata_hints.get("column_mapping", {})
    heuristic_added = {c for c, orig in heuristic_mapping.items() if c != orig}
    original_cols = [
        str(c) for c in result.df.columns
        if not str(c).startswith("_") and str(c) not in heuristic_added
    ]
    if not original_cols:
        return 0.0
    return estimate_cost_chf(result.df[original_cols])


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
    lines = [line for line in text.splitlines()[1:] if line.strip()]
    sample = lines[:20]
    avg_chars = sum(len(line) for line in sample) / max(len(sample), 1)
    total_out = int(len(lines) * avg_chars * 3.0 / chars_per_token)
    # Haiku 4.5 pricing: $1 / 1M input, $5 / 1M output (USD), then USD→CHF.
    cost_usd = total_in / 1_000_000 * 1.0 + total_out / 1_000_000 * 5.0
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

    sanitized_text = df_clean.to_string(index=False)
    cost = _api_cost_estimate(sanitized_text)

    hints = result.metadata_hints
    diagnostics = _build_extraction_diagnostics(result) if mode == "none" else None
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
        map_columns_cost_estimate_chf=_map_columns_cost(result),
        extraction_diagnostics=diagnostics,
    )


@router.post("/offer/map-columns", response_model=MapColumnsResponse)
async def map_offer_columns(body: MapColumnsRequest) -> MapColumnsResponse:
    """
    Run Claude Haiku column mapping on a previously uploaded file.
    Returns the detected field mapping and re-runs local extraction with improved columns.
    """
    entry = file_store.get(body.file_id)
    if entry is None:
        raise HTTPException(404, "Datei nicht gefunden oder abgelaufen. Bitte erneut hochladen.")

    file_bytes, filename = entry
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(500, "ANTHROPIC_API_KEY nicht gesetzt.")

    result, _, _ = _parse_file(file_bytes, filename, None)

    # The heuristic (_add_canonical_columns) adds canonical columns to result.df
    # while keeping the originals. We must exclude those heuristic-added columns
    # so Claude only sees the real original columns from the file.
    heuristic_mapping = result.metadata_hints.get("column_mapping", {})
    heuristic_added = {
        canonical for canonical, original in heuristic_mapping.items()
        if canonical != original
    }
    original_cols = [
        str(c) for c in result.df.columns
        if not str(c).startswith("_") and str(c) not in heuristic_added
    ]
    n_total = len(original_cols)

    df_for_claude = result.df[original_cols]
    mapping = map_columns(df_for_claude, api_key)
    applied: dict[str, str] = {}
    if mapping:
        result.df, applied = apply_mapping(result.df, mapping)
        result.metadata_hints["column_mapping"] = applied

    mapped_originals = set(applied.values())
    unmapped = [c for c in original_cols if c not in mapped_originals]

    products_df = _build_local_extraction(result)
    products: list[dict] = []
    if products_df is not None:
        products_df = _enforce_import_truth(products_df, result.df)
        source_sheet = result.metadata_hints.get("source_sheet")
        extraction_cache.save(extraction_cache.cache_key(file_bytes, source_sheet), products_df)
        extraction_cache.save(extraction_cache.cache_key(file_bytes), products_df)
        products = [_row_to_dict(row) for row in dataframe_to_product_rows(products_df)]

    return MapColumnsResponse(
        mapped_fields=applied,
        columns_total=n_total,
        columns_mapped=len(applied),
        unmapped_columns=unmapped,
        products=products,
    )


@router.post("/offer/column-options", response_model=ColumnOptionsResponse)
async def offer_column_options(body: ColumnOptionsRequest) -> ColumnOptionsResponse:
    """Columns + sample values + current mapping (heuristic + prior) for the manual UI."""
    entry = file_store.get(body.file_id)
    if entry is None:
        raise HTTPException(404, "Datei nicht gefunden oder abgelaufen. Bitte erneut hochladen.")

    file_bytes, filename = entry
    result, original_cols, current = _read_for_mapping(file_bytes, filename, body.prior_mapping)
    columns = [
        {"name": c, "samples": _sample_values(result.df[c])} for c in original_cols
    ]
    return ColumnOptionsResponse(
        columns=columns, current_mapping=current, fields=list(CANONICAL_FIELDS),
    )


@router.post("/offer/remap", response_model=MapColumnsResponse)
async def offer_remap(body: RemapRequest) -> MapColumnsResponse:
    """Apply a user-supplied column mapping and re-run local extraction (no AI).

    Only fields present in the request are touched: a non-empty value overrides the
    heuristic, an empty value clears a previously selectable mapping. Auto-derived
    columns (e.g. size from a size-matrix) are left intact when untouched.
    """
    entry = file_store.get(body.file_id)
    if entry is None:
        raise HTTPException(404, "Datei nicht gefunden oder abgelaufen. Bitte erneut hochladen.")

    file_bytes, filename = entry
    result, original_cols, current = _read_for_mapping(file_bytes, filename, body.prior_mapping)
    df = result.df

    # Materialize the base mapping (heuristic + prior) onto the DataFrame so fields
    # only the AI mapper resolved (e.g. SKU) survive even when the user only edits
    # an unrelated field in the manual dialog.
    for canonical, src in current.items():
        if src in df.columns and canonical not in df.columns:
            df[canonical] = df[src]
    applied = dict(current)

    for canonical in CANONICAL_FIELDS:
        if canonical not in body.mapping:
            continue
        src = (body.mapping.get(canonical) or "").strip()
        if src and src in df.columns:
            df[canonical] = df[src]
            applied[canonical] = src
        elif not src:
            applied.pop(canonical, None)
            if canonical in df.columns:
                df = df.drop(columns=[canonical])

    result.df = df
    result.metadata_hints["column_mapping"] = applied

    products_df = _build_local_extraction(result)
    products: list[dict] = []
    if products_df is not None:
        products_df = _enforce_import_truth(products_df, result.df)
        source_sheet = result.metadata_hints.get("source_sheet")
        extraction_cache.save(extraction_cache.cache_key(file_bytes, source_sheet), products_df)
        extraction_cache.save(extraction_cache.cache_key(file_bytes), products_df)
        products = [_row_to_dict(row) for row in dataframe_to_product_rows(products_df)]

    mapped_originals = set(applied.values())
    unmapped = [c for c in original_cols if c not in mapped_originals]
    return MapColumnsResponse(
        mapped_fields=applied,
        columns_total=len(original_cols),
        columns_mapped=len(applied),
        unmapped_columns=unmapped,
        products=products,
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
    is_raw_fallback = result.metadata_hints.get("was_raw_fallback", False)

    col_mapping = map_columns(result.df, api_key)
    if col_mapping:
        result.df, applied = apply_mapping(result.df, col_mapping)
        result.metadata_hints["column_mapping"] = applied

    df_view = result.df
    df_clean, _ = sanitize_dataframe(df_view)
    sanitized_text = df_clean.to_string(index=False)

    # When the reader fell back to raw data (all heuristics produced 0 rows),
    # also include the truly unprocessed sheet so the AI sees the original layout
    # and is not misled by heuristic column names that may be wrong.
    if is_raw_fallback:
        source_sheet = result.metadata_hints.get("source_sheet")
        try:
            xl_raw = pd.ExcelFile(io.BytesIO(file_bytes))
            _sheet = source_sheet or xl_raw.sheet_names[0]
            df_truly_raw = xl_raw.parse(_sheet, header=None, dtype=str, nrows=100)
            raw_text = df_truly_raw.fillna("").to_string(index=False, header=False)
            sanitized_text = (
                "=== RAW SHEET (first 100 rows, no header processing) ===\n"
                + raw_text
                + "\n\n=== PROCESSED VIEW ===\n"
                + sanitized_text
            )
        except Exception:
            pass  # raw sheet unavailable; proceed with processed view only

    hint_parts: list[str] = []
    if body.profile_name:
        profile = _repo.load(body.profile_name)
        if profile:
            hint_parts.append(profile_to_hints(profile))
    if result.metadata_hints.get("layout_type"):
        hint_parts.append(f"Detected offer layout: {result.metadata_hints['layout_type']}.")
    if is_raw_fallback:
        hint_parts.append(
            "Automatic layout detection failed. "
            "The table shows raw unprocessed sheet data. "
            "Column names may be incorrect or absent. "
            "Extract all identifiable product records regardless of missing fields."
        )
    if result.was_unpivoted:
        hint_parts.append(
            "Data was unpivoted: '_size_from_col' = size, "
            "'_qty_from_col' = available_qty. ordered_qty must remain null."
        )
    if result.metadata_hints.get("detected_currency"):
        hint_parts.append(f"Detected currency: {result.metadata_hints['detected_currency']}")

    hints_str = " | ".join(hint_parts)

    try:
        # extract_line_items is blocking (many API calls); run it off the event
        # loop so other requests stay responsive during a large extraction.
        items, usage = await run_in_threadpool(
            extract_line_items, sanitized_text, hints_str, api_key, get_call_fn(api_key)
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(502, f"AI-Extraktion fehlgeschlagen: {exc}") from exc

    df_extracted = pd.DataFrame(items)
    df_extracted = _enforce_import_truth(df_extracted, result.df)

    source_sheet = result.metadata_hints.get("source_sheet")
    extraction_cache.save(extraction_cache.cache_key(file_bytes, source_sheet), df_extracted)
    extraction_cache.save(extraction_cache.cache_key(file_bytes), df_extracted)

    products = [_row_to_dict(row) for row in dataframe_to_product_rows(df_extracted)]
    return ExtractResponse(
        mode="api",
        products=products,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
    )


def _offer_lines_from_df(df: pd.DataFrame) -> list[OfferLine]:
    """Map an enriched (priced) DataFrame to archived OfferLine entities."""
    records = df.where(pd.notna(df), None).to_dict("records")
    lines: list[OfferLine] = []
    for pos, rec in enumerate(records):
        qty = rec.get("ordered_qty")
        if qty is None:
            qty = rec.get("qty")
        lines.append(
            OfferLine(
                position=pos,
                sku=rec.get("sku"),
                ean=rec.get("ean"),
                product_name=rec.get("product_name"),
                size=rec.get("size"),
                color=rec.get("color"),
                category=rec.get("category"),
                unit_price=_to_float(rec.get("unit_price")),
                currency=rec.get("currency"),
                ordered_qty=_to_int(qty),
                available_qty=_to_int(rec.get("available_qty")),
                discount_pct=_to_float(rec.get("discount_pct")),
                vk_unit=_to_float(rec.get("vk_unit_target")),
                vk_total=_to_float(rec.get("vk_target")),
                margin_actual=_to_float(rec.get("margin_actual")),
                notes=rec.get("notes"),
            )
        )
    return lines


@router.post("/offer/export")
async def export_offer(
    body: ExportRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """
    Apply per-row pricing and generate the AMP reseller Excel, archive the
    offer, and return the .xlsx file as a binary download.
    """
    if not body.rows:
        raise HTTPException(400, "Keine Positionen übergeben.")
    if not body.supplier_name.strip():
        raise HTTPException(400, "Lieferantenname fehlt.")

    rates = body.rates or dict(DEFAULT_RATES)

    enriched_rows: list[pd.DataFrame] = []
    for row in body.rows:
        row_dict = row.model_dump(exclude={"vk_manual", "margin_pct"})
        if row.vk_manual is not None and row.vk_manual > 0:
            row_dict["vk_target"] = float(row.vk_manual)
        row_df = pd.DataFrame([row_dict])

        enriched = enrich_dataframe(row_df, row.margin_pct, body.target_currency, rates)

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
    today = date.today()
    filename = f"Offerte_{body.supplier_name.replace(' ', '_')}_{today:%Y%m%d}.xlsx"

    # Archive the offer (auto-save). Never let an archive failure block the
    # download the user just generated.
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    try:
        stored = file_store.get(body.file_id)
        if stored is None:
            logger.warning("Original file %s not in store; archiving without it", body.file_id)
            original_bytes, original_filename = b"", ""
        else:
            original_bytes, original_filename = stored

        offer = Offer(
            jahr=today.year,
            marke=(body.marke.strip() or "Unbekannt"),
            lieferant=body.supplier_name.strip(),
            created_by_name=user.name,
            created_by_user_id=user.id,
            target_currency=body.target_currency,
            default_margin=body.default_margin_pct,
            original_filename=original_filename,
            generated_filename=filename,
            status=OfferStatus.CREATED,
            line_items=_offer_lines_from_df(enriched_df),
        )
        saved = SqlOfferRepository(db).create(offer, original_bytes, excel_bytes)
        headers["X-Offer-Id"] = str(saved.id)
        headers["Access-Control-Expose-Headers"] = "X-Offer-Id"
    except Exception:
        logger.exception("Offerte konnte nicht archiviert werden")

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
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
    sem = asyncio.Semaphore(5)

    async def _fetch(ean: str) -> None:
        async with sem:
            price = await loop.run_in_executor(None, scraper.fetch_price, ean)
            results.append((ean, price))
            await asyncio.sleep(0.5)

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

@router.get("/rates")
def get_rates() -> dict:
    """Return exchange rates (format: 1 CHF = X foreign) plus a freshness marker.

    Tries the live ECB daily feed first; on any failure falls back to the static
    DEFAULT_RATES so the create flow always has something to display. The static
    rates are merged underneath the live ones, so currencies missing from the ECB
    feed still resolve.
    """
    live = fetch_ecb_rates()
    if live is not None:
        rates, date_str = live
        return {"rates": {**DEFAULT_RATES, **rates}, "date": date_str, "live": True}
    return {"rates": dict(DEFAULT_RATES), "date": None, "live": False}


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
