"""Mapping helpers from current backend objects to future UI contracts."""

from __future__ import annotations

import math
from datetime import date
from typing import Any

import pandas as pd

from offerten_converter.api.schemas import (
    ExportPreview,
    FileMetadata,
    PrepareFileState,
    PricingSummary,
    ProductRow,
    Requirement,
    RequirementStatus,
    WorkflowStep,
    WorkflowStepInfo,
)


def _clean_scalar(value: Any) -> Any:
    """Return JSON-safe scalar values, converting blank/NaN to None."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return value


def _to_float(value: Any) -> float | None:
    value = _clean_scalar(value)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    value = _clean_scalar(value)
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def build_workflow_steps(
    active_step: WorkflowStep,
    completed_steps: set[WorkflowStep] | None = None,
) -> list[WorkflowStepInfo]:
    """Build the static four-step rail with active/completed state."""
    completed = completed_steps or set()
    steps = [
        (WorkflowStep.PREPARE_FILE, "Datei vorbereiten", "Lieferant und Datei prüfen"),
        (WorkflowStep.RECOGNIZE_PRODUCTS, "Produkte erkennen", "Positionen extrahieren"),
        (WorkflowStep.REVIEW_PRICES, "Preise prüfen", "Mengen und Margen setzen"),
        (WorkflowStep.EXPORT_OFFER, "Export erstellen", "Offerte herunterladen"),
    ]
    return [
        WorkflowStepInfo(
            step=step,
            index=index,
            label=label,
            description=description,
            active=step == active_step,
            completed=step in completed,
        )
        for index, (step, label, description) in enumerate(steps, start=1)
    ]


def build_prepare_requirements(
    supplier_name: str,
    has_file: bool,
    has_profile: bool,
) -> list[Requirement]:
    """Build the screen-1 required field checklist."""
    supplier_ok = bool(supplier_name.strip())
    return [
        Requirement(
            key="supplier",
            label="Lieferant",
            description="Wird lokal für Profil, Export-Dateiname und Zuordnung benötigt.",
            status=RequirementStatus.OK if supplier_ok else RequirementStatus.MISSING,
        ),
        Requirement(
            key="file",
            label="Excel-Datei",
            description="Offerte mit Artikeln, Varianten, Preisen und Verfügbarkeit.",
            status=RequirementStatus.OK if has_file else RequirementStatus.MISSING,
        ),
        Requirement(
            key="profile",
            label="Profil",
            description="Optional. Spart Arbeit bei wiederkehrenden Lieferanten.",
            status=RequirementStatus.OK if has_profile else RequirementStatus.OPTIONAL,
            required=False,
        ),
    ]


def build_prepare_state(
    supplier_name: str,
    selected_profile: str | None,
    file_metadata: FileMetadata | None,
) -> PrepareFileState:
    """Build screen-1 state from current UI/session values."""
    requirements = build_prepare_requirements(
        supplier_name=supplier_name,
        has_file=file_metadata is not None,
        has_profile=bool(selected_profile),
    )
    required_ok = all(
        item.status == RequirementStatus.OK for item in requirements if item.required
    )
    return PrepareFileState(
        supplier_name=supplier_name,
        selected_profile=selected_profile,
        file=file_metadata,
        requirements=requirements,
        can_continue=required_ok,
    )


def read_result_to_file_metadata(
    *,
    filename: str,
    size_bytes: int,
    sheet_names: list[str],
    recommended_sheet: str | None,
    selected_sheet: str | None,
    result: Any,
) -> FileMetadata:
    """Map an Excel reader result to UI file metadata."""
    hints = getattr(result, "metadata_hints", {}) or {}
    mapping = hints.get("column_mapping") or {}
    return FileMetadata(
        filename=filename,
        size_bytes=size_bytes,
        sheet_names=sheet_names,
        recommended_sheet=recommended_sheet,
        selected_sheet=selected_sheet,
        row_count=len(result.df),
        column_count=len(result.df.columns),
        detected_currency=hints.get("detected_currency"),
        layout_type=hints.get("layout_type"),
        was_unpivoted=bool(getattr(result, "was_unpivoted", False)),
        unpivot_info=str(getattr(result, "unpivot_info", "") or ""),
        column_mapping={str(key): str(value) for key, value in mapping.items()},
    )


def dataframe_to_product_rows(df: pd.DataFrame) -> list[ProductRow]:
    """Convert an extracted product DataFrame into stable row DTOs."""
    rows: list[ProductRow] = []
    for index, row in df.reset_index(drop=True).iterrows():
        missing_price = _to_float(row.get("unit_price")) is None
        missing_qty = _to_int(row.get("ordered_qty")) is None
        status = RequirementStatus.OK
        if missing_price:
            status = RequirementStatus.WARNING
        if missing_qty:
            status = RequirementStatus.MISSING
        rows.append(
            ProductRow(
                row_id=index,
                sku=_clean_scalar(row.get("sku")),
                ean=_clean_scalar(row.get("ean")),
                product_name=_clean_scalar(row.get("product_name")),
                size=_clean_scalar(row.get("size")),
                color=_clean_scalar(row.get("color")),
                category=_clean_scalar(row.get("category")),
                unit_price=_to_float(row.get("unit_price")),
                currency=_clean_scalar(row.get("currency")),
                ordered_qty=_to_int(row.get("ordered_qty")),
                available_qty=_to_int(row.get("available_qty")),
                discount_pct=_to_float(row.get("discount_pct")),
                notes=_clean_scalar(row.get("notes")),
                status=status,
            )
        )
    return rows


def pricing_summary_from_enriched_df(
    enriched_df: pd.DataFrame,
    target_currency: str,
) -> PricingSummary:
    """Build screen-3 pricing summary from enriched pricing data."""
    missing_qty = 0
    if "qty" in enriched_df.columns:
        missing_qty = int(enriched_df["qty"].isna().sum())

    missing_price = 0
    if "ek_unit_target" in enriched_df.columns:
        missing_price = int(enriched_df["ek_unit_target"].isna().sum())

    unknown_currency = 0
    if "_unknown_currency" in enriched_df.columns:
        unknown_currency = int(enriched_df["_unknown_currency"].fillna(False).astype(bool).sum())

    ek_total = _to_float(enriched_df.get("ek_target", pd.Series(dtype=float)).sum(skipna=True))
    vk_total = _to_float(enriched_df.get("vk_target", pd.Series(dtype=float)).sum(skipna=True))
    average_margin = _to_float(
        enriched_df.get("margin_actual", pd.Series(dtype=float)).mean(skipna=True)
    )
    can_continue = missing_qty == 0 and missing_price == 0 and not enriched_df.empty

    return PricingSummary(
        product_count=len(enriched_df),
        missing_qty_count=missing_qty,
        missing_price_count=missing_price,
        unknown_currency_count=unknown_currency,
        ek_total=ek_total,
        vk_total=vk_total,
        average_margin_pct=average_margin,
        target_currency=target_currency,
        can_continue=can_continue,
    )


def build_export_preview(
    *,
    supplier_name: str,
    created_by: str,
    target_currency: str,
    valid_days: int,
    product_count: int,
    missing_qty_count: int,
    missing_price_count: int,
) -> ExportPreview:
    """Build screen-4 export readiness state."""
    supplier_ok = bool(supplier_name.strip())
    positions_ok = product_count > 0
    quantities_ok = missing_qty_count == 0
    prices_ok = missing_price_count == 0
    safe_supplier = supplier_name.strip().replace(" ", "_") or "Lieferant"
    filename = f"Offerte_{safe_supplier}_{date.today():%Y%m%d}.xlsx"
    requirements = [
        Requirement(
            key="supplier",
            label="Lieferant",
            description="Muss gesetzt sein, damit die Offerte eindeutig benannt werden kann.",
            status=RequirementStatus.OK if supplier_ok else RequirementStatus.MISSING,
        ),
        Requirement(
            key="positions",
            label="Positionen",
            description="Mindestens eine erkannte Produktposition muss vorhanden sein.",
            status=RequirementStatus.OK if positions_ok else RequirementStatus.MISSING,
        ),
        Requirement(
            key="quantities",
            label="Mengen",
            description="Alle exportierten Positionen brauchen eine Menge.",
            status=RequirementStatus.OK if quantities_ok else RequirementStatus.MISSING,
        ),
        Requirement(
            key="prices",
            label="Preise",
            description="Alle exportierten Positionen brauchen einen EK/VK.",
            status=RequirementStatus.OK if prices_ok else RequirementStatus.MISSING,
        ),
    ]
    return ExportPreview(
        supplier_name=supplier_name,
        created_by=created_by,
        target_currency=target_currency,
        valid_days=valid_days,
        product_count=product_count,
        filename=filename,
        requirements=requirements,
        can_download=supplier_ok and positions_ok and quantities_ok and prices_ok,
    )

