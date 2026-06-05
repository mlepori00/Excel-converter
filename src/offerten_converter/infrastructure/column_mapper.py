"""Map raw supplier Excel column headers to canonical field names via Claude."""

from __future__ import annotations

import json
import logging
import re

import pandas as pd

logger = logging.getLogger(__name__)

CANONICAL_FIELDS = [
    "sku", "ean", "product_name", "size", "color", "category",
    "available_qty", "ordered_qty", "unit_price", "currency", "discount_pct",
]

_SYSTEM_PROMPT = (
    "You are a column mapping assistant for supplier product offer Excel files. "
    "Your job: map each column header to one of these canonical fields, or null if no match.\n\n"
    "Canonical fields:\n"
    "- sku: internal article code / model number (NOT an EAN barcode)\n"
    "- ean: EAN, GTIN, UPC barcode (typically 13 digits)\n"
    "- product_name: product name or model description (human-readable text)\n"
    "- size: size (EU/US shoe size, clothing size XS/S/M/L/XL, etc.)\n"
    "- color: color name or code\n"
    "- category: category, collection, product line, season\n"
    "- available_qty: available stock / inventory quantity\n"
    "- ordered_qty: customer order quantity (often blank in offer sheets)\n"
    "- unit_price: purchase price per unit (Net/Offer/Wholesale, NOT retail/RRP)\n"
    "- currency: currency code (CHF, EUR, USD...)\n"
    "- discount_pct: discount as a percentage\n\n"
    "Rules:\n"
    "- Each canonical field can be assigned to AT MOST ONE column\n"
    "- If multiple price columns exist, pick the trade price "
    "(Net/Offer/Wholesale) over retail/RRP\n"
    "- 'Model' is product_name if values look like names (Arizona, Air Max 90); "
    "it is sku if values look like codes (BK-1234, ART-567)\n"
    "- Columns with no matching canonical field: assign null\n"
    "- Return ONLY valid JSON, no markdown, no explanation: "
    "{\"ColumnHeader\": \"canonical_field_or_null\", ...}"
)


_HAIKU_INPUT_USD_PER_M = 1.00   # observed from OpenRouter/Bedrock billing
_HAIKU_OUTPUT_USD_PER_M = 5.00
_CHF_PER_USD = 0.89


def estimate_cost_chf(df: pd.DataFrame, n_samples: int = 5) -> float:
    """Estimate CHF cost of a map_columns call without hitting the API."""
    headers = [str(c) for c in df.columns if not str(c).startswith("_")]
    if not headers:
        return 0.0
    user_content = _build_prompt(df, headers, n_samples)
    # Claude tokenizer averages ~3.5 chars/token (not 4) for mixed header/value text
    chars_per_token = 3.5
    input_tokens = int((len(_SYSTEM_PROMPT) + len(user_content)) / chars_per_token)
    # Output: JSON dict with each header name + canonical value; avg ~45 chars/entry
    output_chars = sum(len(h) + 20 for h in headers) + 20
    output_tokens = max(40, int(output_chars / chars_per_token))
    cost_usd = (
        input_tokens * _HAIKU_INPUT_USD_PER_M + output_tokens * _HAIKU_OUTPUT_USD_PER_M
    ) / 1_000_000
    return round(cost_usd * _CHF_PER_USD, 5)


def map_columns(df: pd.DataFrame, api_key: str, n_samples: int = 5) -> dict[str, str]:
    """Send column headers + sampled rows to Claude.

    Returns {original_column_name: canonical_field} for matched columns only.
    Falls back to empty dict (heuristics still apply) if the API call fails.
    """
    headers = [str(c) for c in df.columns if not str(c).startswith("_")]
    if not headers or not api_key:
        return {}

    user_content = _build_prompt(df, headers, n_samples)
    try:
        raw = _call_claude(api_key, user_content)
        mapping = _parse_response(raw, headers)
        logger.info("Claude column mapping: %s", mapping)
        return mapping
    except Exception as exc:
        logger.warning("Column mapping failed, falling back to heuristics: %s", exc)
        return {}


def apply_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> tuple[pd.DataFrame, dict[str, str]]:
    """Apply a column mapping to df, adding/overwriting canonical columns.

    Returns (updated_df, mapping) where mapping reflects what was applied.
    """
    if not mapping:
        return df, {}
    df = df.copy()
    applied: dict[str, str] = {}
    for original, canonical in mapping.items():
        if original in df.columns:
            df[canonical] = df[original]
            applied[canonical] = original
    return df, applied


def _build_prompt(df: pd.DataFrame, headers: list[str], n_samples: int) -> str:
    n_rows = len(df)
    if n_rows == 0:
        return f"Columns: {', '.join(headers)}\n(No data rows)"

    step = max(1, n_rows // n_samples)
    indices = [min(i * step, n_rows - 1) for i in range(n_samples)]

    lines = ["Column | Sample values", "--- | ---"]
    for col in headers:
        samples = []
        for i in indices:
            try:
                v = str(df.iloc[i][col]).strip()
            except (KeyError, IndexError):
                continue
            if v and v.lower() not in ("nan", "none", ""):
                samples.append(v)
        unique = list(dict.fromkeys(samples))[:3]
        sample_str = " | ".join(unique) if unique else "(empty)"
        lines.append(f"{col} | {sample_str}")

    return "\n".join(lines)


def _call_claude(api_key: str, user_content: str) -> str:
    if api_key.startswith("sk-or-"):
        return _call_openrouter(api_key, user_content)
    return _call_anthropic(api_key, user_content)


def _call_anthropic(api_key: str, user_content: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    return message.content[0].text.strip()


def _call_openrouter(api_key: str, user_content: str) -> str:
    import httpx
    response = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "anthropic/claude-haiku-4-5",
            "max_tokens": 512,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def _parse_response(raw: str, headers: list[str]) -> dict[str, str]:
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")
    data = json.loads(raw)

    result: dict[str, str] = {}
    used_canonical: set[str] = set()
    for col, canonical in data.items():
        if col not in headers:
            continue
        if not canonical or str(canonical).lower() in ("null", "none", ""):
            continue
        if canonical not in CANONICAL_FIELDS:
            continue
        if canonical in used_canonical:
            logger.warning("Duplicate canonical '%s' for column '%s', skipping", canonical, col)
            continue
        result[col] = canonical
        used_canonical.add(canonical)
    return result
