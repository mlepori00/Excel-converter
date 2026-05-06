"""Use case: filter extracted line items by a free-text query using fuzzy matching."""

from __future__ import annotations

import pandas as pd
from rapidfuzz import fuzz

# Fields searched per row (in order of relevance)
_SEARCH_FIELDS = ["product_name", "category", "sku", "ean", "color", "notes"]

# A substring match scores 100 – we only need fuzzy for approximate terms
_FUZZY_THRESHOLD = 72


def _row_text(row: pd.Series) -> str:
    """Build a single searchable string from all relevant fields of a row."""
    parts = []
    for field in _SEARCH_FIELDS:
        val = row.get(field)
        if val is not None and not (isinstance(val, float) and pd.isna(val)):
            parts.append(str(val).strip())
    # Also include extra_fields values
    ef = row.get("extra_fields")
    if isinstance(ef, dict):
        parts.extend(str(v) for v in ef.values() if v is not None)
    return " ".join(parts)


def _matches_term(text: str, term: str) -> bool:
    """Return True if *term* matches *text* via substring or fuzzy ratio."""
    text_lower = text.lower()
    term_lower = term.lower()
    # Fast path: exact substring
    if term_lower in text_lower:
        return True
    # Fuzzy fallback for typos / partial names
    return fuzz.partial_ratio(term_lower, text_lower) >= _FUZZY_THRESHOLD


def filter_line_items(df: pd.DataFrame, query: str) -> tuple[pd.DataFrame, int]:
    """Filter *df* to rows matching *query*.

    - Query can contain multiple comma-separated terms: "Cloud 6, Jacken"
    - A row matches if ANY term matches (OR logic)
    - Matching uses substring check first, then fuzzy ratio fallback
    - Returns (filtered_df, total_count). If query is blank, returns (df, len(df)).
    """
    total = len(df)
    query = query.strip()
    if not query:
        return df, total

    terms = [t.strip() for t in query.split(",") if t.strip()]
    if not terms:
        return df, total

    mask = []
    for _, row in df.iterrows():
        text = _row_text(row)
        matched = any(_matches_term(text, term) for term in terms)
        mask.append(matched)

    filtered = df[mask]
    return filtered, total
