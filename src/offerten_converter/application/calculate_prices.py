"""Use case: enrich a DataFrame with pricing columns."""

from __future__ import annotations

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

from offerten_converter.domain.pricing import (
    DEFAULT_RATES,
    actual_margin,
    calculate_vk,
    convert_to_target,
    margin_color,
)


def enrich_dataframe(
    df: pd.DataFrame,
    margin_pct: float,
    target_currency: str,
    rates: dict | None = None,
) -> pd.DataFrame:
    """Add pricing columns to *df* (operates on a copy).

    Adds: qty, ek_unit_target, ek_target, vk_unit_target, vk_target, margin_actual, margin_color_val
    """
    df = df.copy()
    margin = margin_pct / 100.0
    r = rates or DEFAULT_RATES

    ek_unit_target_list = []
    ek_target_list = []
    vk_unit_target_list = []
    vk_target_list = []
    margin_actual_list = []
    margin_color_list = []
    qty_list = []
    qty_fallback_list = []
    unknown_currency_list = []

    for _, row in df.iterrows():
        price = row.get("unit_price")
        currency = str(row.get("currency") or "CHF").upper()
        disc_pct = row.get("discount_pct") or 0
        min_qty = row.get("min_qty")
        ordered_qty = row.get("ordered_qty")

        try:
            price_f = float(price) if price is not None and str(price).strip() != "" else None
        except (ValueError, TypeError):
            price_f = None
            logger.warning("Could not parse unit_price %r – row will have no EK.", price)

        try:
            disc_f = float(disc_pct) if disc_pct is not None else 0.0
        except (ValueError, TypeError):
            disc_f = 0.0

        qty_fallback_used = False
        try:
            qty_raw = float(ordered_qty)
            if qty_raw <= 0:
                qty_f = 1.0
                qty_fallback_used = True
            else:
                qty_f = qty_raw
        except (TypeError, ValueError):
            try:
                qty_f = max(1.0, float(min_qty))
            except (TypeError, ValueError):
                qty_f = 1.0
            qty_fallback_used = True

        # Per-unit cost after discount, capped to avoid negative prices
        disc_f = max(0.0, min(disc_f, 100.0))
        ek_unit = price_f * (1 - disc_f / 100.0) if price_f is not None else None
        # Convert unit cost to target currency
        ek_unit_conv, currency_unknown = convert_to_target(ek_unit, currency, target_currency, r)
        # Total = unit cost × quantity
        ek_total = ek_unit_conv * qty_f if ek_unit_conv is not None else None

        manual_vk = row.get("vk_target") if "vk_target" in row.index else None
        try:
            if manual_vk is None or (isinstance(manual_vk, str) and manual_vk == ""):
                manual_vk_f = None
            elif pd.isna(manual_vk):
                manual_vk_f = None
            else:
                manual_vk_f = float(manual_vk)
        except (ValueError, TypeError):
            manual_vk_f = None

        # VK per unit, then total
        vk_unit = manual_vk_f if manual_vk_f is not None else calculate_vk(ek_unit_conv, margin)
        vk_total = vk_unit * qty_f if vk_unit is not None else None

        marg = actual_margin(ek_unit_conv, vk_unit)

        qty_list.append(int(qty_f))
        qty_fallback_list.append(qty_fallback_used)
        unknown_currency_list.append(currency_unknown)
        ek_unit_target_list.append(round(ek_unit_conv, 4) if ek_unit_conv is not None else None)
        ek_target_list.append(round(ek_total, 4) if ek_total is not None else None)
        vk_unit_target_list.append(round(vk_unit, 4) if vk_unit is not None else None)
        vk_target_list.append(round(vk_total, 4) if vk_total is not None else None)
        margin_actual_list.append(round(marg * 100, 2) if marg is not None else None)
        margin_color_list.append(margin_color(marg))

    df["qty"] = qty_list
    df["_qty_fallback"] = qty_fallback_list
    df["_unknown_currency"] = unknown_currency_list
    df["ek_unit_target"] = ek_unit_target_list
    df["ek_target"] = ek_target_list
    df["vk_unit_target"] = vk_unit_target_list
    df["vk_target"] = vk_target_list
    df["margin_actual"] = margin_actual_list
    df["margin_color_val"] = margin_color_list

    return df
