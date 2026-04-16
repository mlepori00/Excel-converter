"""Use case: export an enriched DataFrame to Excel bytes."""

from __future__ import annotations

from typing import Callable

import pandas as pd


def export_to_excel(
    df: pd.DataFrame,
    supplier_name: str,
    created_by: str,
    target_currency: str,
    valid_days: int = 30,
    *,
    build_fn: Callable[..., bytes] | None = None,
) -> bytes:
    """Build and return a formatted Excel file as bytes.

    If *build_fn* is None, falls back to the default infrastructure builder.
    """
    if build_fn is None:
        from offerten_converter.infrastructure.excel_writer import build_excel

        build_fn = build_excel
    return build_fn(df, supplier_name, created_by, target_currency, valid_days)
