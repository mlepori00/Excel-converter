"""Pure helpers for parsing numbers out of messy supplier-cell values."""

from __future__ import annotations

import math
import re

_NUMERIC_TOKEN = re.compile(r"[-+]?\d[\d.,'’ ]*")


def parse_decimal(value: object) -> float | None:
    """Parse a number from a possibly messy cell value.

    Supplier offers store prices and quantities as free text: currency symbols
    and codes ("65,00 €", "EUR 89.90"), mojibake (a mis-encoded € arriving as
    replacement characters), thousands separators ("1'234", "1,234.50"), and
    European decimal commas ("65,00", "1.234,50"). The heuristic (no-AI)
    extraction path passes these raw strings straight through, so every
    conversion to a number must tolerate them. Returns None when no number can
    be recovered.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return None if math.isnan(number) else number

    match = _NUMERIC_TOKEN.search(str(value))
    if not match:
        return None
    token = match.group(0).replace("'", "").replace("’", "").replace(" ", "")
    if "," in token and "." in token:
        # The right-most separator is the decimal point.
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token:
        # Comma is a decimal sep only when 1-2 digits follow; otherwise thousands.
        is_decimal = re.search(r",\d{1,2}$", token)
        token = token.replace(",", ".") if is_decimal else token.replace(",", "")
    token = token.rstrip(".,")
    try:
        return float(token)
    except ValueError:
        return None
