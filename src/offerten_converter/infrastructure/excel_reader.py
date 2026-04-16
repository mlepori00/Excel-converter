"""Read Excel/CSV files into pandas DataFrames with smart header detection."""

from __future__ import annotations

import io
import logging

import pandas as pd

logger = logging.getLogger(__name__)


def _detect_header_row(df_raw: pd.DataFrame, max_scan: int = 50) -> int | None:
    """Scan the first *max_scan* rows and return the best header row index.

    Heuristic: a good header row has >= 75% non-null cells and >= 60% string values.
    """
    for i in range(min(max_scan, len(df_raw))):
        row = df_raw.iloc[i]
        non_null = row.notna().sum()
        total = len(row)
        if total == 0:
            continue
        fill_ratio = non_null / total
        str_ratio = sum(1 for v in row if isinstance(v, str)) / total
        if fill_ratio >= 0.75 and str_ratio >= 0.60:
            return i
    return None


def get_sheet_names(file_bytes: bytes, filename: str) -> list[str]:
    """Return sheet names for an Excel file. Empty list for CSV."""
    lower = filename.lower()
    if lower.endswith(".csv"):
        return []
    try:
        xl = pd.ExcelFile(io.BytesIO(file_bytes))
        return xl.sheet_names
    except Exception as exc:
        logger.error("Could not read sheet names: %s", exc)
        return []


def read_excel(
    file_bytes: bytes,
    filename: str,
    sheet_name: str | None = None,
) -> pd.DataFrame:
    """Read an uploaded file into a DataFrame with smart header detection.

    Returns the DataFrame with detected headers. Raises ValueError on failure.
    """
    lower = filename.lower()
    try:
        if lower.endswith(".csv"):
            df_raw = pd.read_csv(io.BytesIO(file_bytes), header=None)
        elif lower.endswith(".xls") and not lower.endswith(".xlsx"):
            df_raw = pd.read_excel(
                io.BytesIO(file_bytes), sheet_name=sheet_name or 0,
                header=None, engine="xlrd",
            )
        else:
            df_raw = pd.read_excel(
                io.BytesIO(file_bytes), sheet_name=sheet_name or 0,
                header=None, engine="openpyxl",
            )
    except Exception as exc:
        raise ValueError(f"Datei konnte nicht gelesen werden: {exc}") from exc

    header_idx = _detect_header_row(df_raw)
    if header_idx is not None and header_idx > 0:
        df_raw.columns = df_raw.iloc[header_idx]
        df_raw = df_raw.iloc[header_idx + 1:].reset_index(drop=True)
    elif header_idx == 0:
        df_raw.columns = df_raw.iloc[0]
        df_raw = df_raw.iloc[1:].reset_index(drop=True)

    # Drop fully empty rows and columns
    df_raw = df_raw.dropna(how="all").dropna(axis=1, how="all")

    logger.info("Read file: %d rows, %d columns", len(df_raw), len(df_raw.columns))
    return df_raw
