"""Use case: sanitize a DataFrame by removing PII before any API call."""

from __future__ import annotations

import logging
import re
from typing import Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# Regex patterns for sensitive cell content
_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.I),
    "phone": re.compile(
        r"\+\d{1,3}[\s\.\-]\d{1,4}[\s\.\-]\d{2,5}(?:[\s\.\-]\d{2,4})?"
        r"|\b0\d{1,3}[\s\.\-]\d{3,5}[\s\.\-]\d{2,4}\b",
    ),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
    "vat_ch": re.compile(r"\bCHE[\-\.]?\d{3}[\.\-]?\d{3}[\.\-]?\d{3}\b", re.I),
    "vat_eu": re.compile(r"\b[A-Z]{2}\d{8,12}\b"),
    "uid": re.compile(r"\bUID[\-\s]?CHE[\-\.]?\d{3}[\.\-]?\d{3}[\.\-]?\d{3}\b", re.I),
}

# Sensitive column keywords
_EXACT_WORD_SENSITIVE = frozenset([
    "email", "mail", "fax", "iban", "bic", "swift",
])

_SUBSTRING_SENSITIVE = [
    "lieferant", "supplier", "vendor",
    "kunde", "kunden", "customer", "empfänger", "empfaenger", "recipient",
    "telefon", "phone", "mobil", "mobile",
    "adresse", "address", "strasse", "straße", "street", "postfach",
    "kontakt", "contact", "ansprechpartner",
    "umsatzsteuer", "ust-id", "ust_id", "vatid", "vat-id",
    "uid-nummer", "uid_nummer", "mwst-nr", "steuernummer",
    "lieferantenname", "kundenname", "firmenname", "empfängername",
    "kundennamen", "firmen-name",
]


def _col_is_sensitive(col_name: str) -> bool:
    lower = str(col_name).lower().strip()

    if re.match(r"^unnamed:\s*\d+$", lower):
        return False

    for kw in _SUBSTRING_SENSITIVE:
        if kw in lower:
            return True

    for kw in _EXACT_WORD_SENSITIVE:
        if re.search(rf"\b{re.escape(kw)}\b", lower):
            return True

    return False


def _cell_contains_pii(value: str) -> bool:
    return any(p.search(value) for p in _PATTERNS.values())


def sanitize_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, list[str]]:
    """Remove sensitive columns and scrub PII from remaining cell values."""
    removed: list[str] = []
    df = df.copy()

    cols_to_drop = [c for c in df.columns if _col_is_sensitive(str(c))]
    if cols_to_drop:
        for col in cols_to_drop:
            lower = str(col).lower()
            reason = "matched sensitive keyword"
            for kw in _SUBSTRING_SENSITIVE:
                if kw in lower:
                    reason = f"enthält '{kw}'"
                    break
            for kw in _EXACT_WORD_SENSITIVE:
                if re.search(rf"\b{re.escape(kw)}\b", lower):
                    reason = f"enthält Wort '{kw}'"
                    break
            removed.append(f"Spalte entfernt: '{col}' ({reason})")
        df.drop(columns=cols_to_drop, inplace=True)
        logger.info("Sanitizer dropped columns: %s", cols_to_drop)

    for col in df.columns:
        if df[col].dtype == object:
            for idx, val in df[col].items():
                if not isinstance(val, str):
                    continue
                for pattern_name, pattern in _PATTERNS.items():
                    if pattern.search(val):
                        val = pattern.sub("[REDACTED]", val)
                        removed.append(
                            f"Zelle [{idx}, '{col}']: {pattern_name} geschwärzt"
                        )
                df.at[idx, col] = val

    if not removed:
        logger.info("Sanitizer: no sensitive data found.")

    return df, removed
