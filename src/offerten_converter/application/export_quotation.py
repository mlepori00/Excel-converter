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

    The concrete Excel builder is injected by the composition layer.
    """
    if build_fn is None:
        raise RuntimeError(
            "Kein Excel-Builder übergeben. Bitte build_fn via Dependency Injection setzen."
        )
    return build_fn(df, supplier_name, created_by, target_currency, valid_days)
