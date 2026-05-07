"""Use case: extract product line items from sanitized text via AI."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

CHUNK_SIZE = 50  # default fallback; overridden by _calculate_chunk_size()

# Stay well under the 8192 output token limit
_TARGET_OUTPUT_TOKENS = 5_000
# JSON output is roughly 3× the raw input row (field names + structure overhead)
_JSON_OVERHEAD = 3.0
_CHARS_PER_TOKEN = 4

SYSTEM_PROMPT = (
    "You are a data extraction assistant. Extract all product line items from this "
    "supplier quotation table. Return ONLY a JSON array, no markdown, no explanation. "
    "Standard fields: sku, ean, product_name, size, color, category, "
    "unit_price (number, price per single piece), "
    "currency (ISO), "
    "ordered_qty (int, the quantity actually ordered or requested in this transaction. "
    "Look for columns named ORDER, BESTELLUNG, QTY ORDERED, QUANTITY ORDERED, ORDERED. "
    "Use the exact value, even if 0. Never substitute 0 with 1. "
    "If no order-quantity column exists, use null – do NOT use stock or availability numbers here), "
    "available_qty (int, the available stock or inventory quantity. "
    "Look for columns named AVAILABLE, TOTAL, STOCK, LAGER, VERFÜGBAR, QTY AVAILABLE, BESTAND. "
    "If no availability column exists, use null), "
    "min_qty (int, minimum order quantity if stated separately, else null), "
    "discount_pct (number 0-100, convert decimal fractions: 0.05 → 5, 0.1 → 10), "
    "notes. "
    "Use null for missing standard fields. "
    "IMPORTANT – unit_price must always be in the original currency as written in the file. "
    "Never convert currencies. Extract the raw number only. "
    "If multiple price columns exist (e.g. RETAIL, WHOLESALE, OFFER PRICE, NET PRICE, "
    "UNIT PRICE, LIST PRICE), always use the column that represents the actual price "
    "charged in this specific transaction (typically labeled OFFER PRICE, NET PRICE, "
    "ORDER PRICE, or INVOICE PRICE). Use WHOLESALE or LIST PRICE only if no "
    "transaction-specific price column exists. "
    "If discount is already applied to unit_price, set discount_pct=0. "
    "Skip any summary, subtotal, or total rows. "
    "IMPORTANT – extra_fields: any column that contains useful product information "
    "(alternative codes, reference numbers, article IDs, URLs, delivery dates, "
    "availability status, style numbers, etc.) that does not fit a standard field "
    "must be captured in 'extra_fields' as a JSON object {column_name: value}. "
    "Never discard a column that could identify or describe the product. "
    "If nothing is left over, set extra_fields to {}."
)

REQUIRED_FIELDS = [
    "sku", "ean", "product_name", "size", "color", "category",
    "unit_price", "currency", "ordered_qty", "available_qty", "min_qty",
    "discount_pct", "notes", "extra_fields",
]


def _normalize_item(item: dict) -> dict:
    """Ensure every required field is present (null / {} if absent)."""
    normalized = {field: item.get(field) for field in REQUIRED_FIELDS}
    # extra_fields must always be a dict, never null
    ef = normalized.get("extra_fields")
    if not isinstance(ef, dict):
        normalized["extra_fields"] = {}
    return normalized


def _repair_truncated_json(raw: str) -> str:
    """Attempt to salvage a truncated JSON array.

    Strategy: find the last complete object (ends with '}, ' or '}]') and
    close the array there. This is safer than rfind('}') which can match
    inside nested dicts (e.g. extra_fields: {"color": {"R": 255}}).
    """
    # Try progressively shorter tails until we get valid JSON
    # Look for boundaries that indicate a complete top-level object:
    # '}, ' (comma between objects) or '}' right before end-of-array
    candidates = []
    pos = 0
    while True:
        idx = raw.find("},", pos)
        if idx == -1:
            break
        candidates.append(idx + 1)   # include the '}'
        pos = idx + 1

    # Also try the raw rfind('}') as last resort
    last_brace = raw.rfind("}")
    if last_brace != -1 and last_brace not in candidates:
        candidates.append(last_brace)

    if not candidates:
        raise ValueError("No complete JSON object found in response.")

    # Try from longest to shortest
    for cut in sorted(candidates, reverse=True):
        repaired = raw[:cut + 1].rstrip().rstrip(",") + "]"
        try:
            json.loads(repaired)
            logger.info("JSON repaired at position %d (of %d).", cut, len(raw))
            return repaired
        except json.JSONDecodeError:
            continue

    raise ValueError("Cannot repair truncated JSON – no valid cut point found.")


def _parse_response(raw: str) -> list[dict]:
    """Parse AI response into a list of dicts, with truncation recovery."""
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(line for line in lines if not line.startswith("```")).strip()

    bracket = raw.find("[")
    if bracket > 0:
        raw = raw[bracket:]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("JSON parse failed (%s) – attempting repair.", exc)
        try:
            raw = _repair_truncated_json(raw)
            data = json.loads(raw)
            logger.info("JSON repaired successfully.")
        except (json.JSONDecodeError, ValueError) as exc2:
            raise ValueError(
                f"Claude returned invalid JSON: {exc}\n\nRaw response:\n{raw}"
            ) from exc2

    if not isinstance(data, list):
        raise ValueError(
            f"Expected a JSON array but got {type(data).__name__}.\n\nRaw response:\n{raw}"
        )
    return [_normalize_item(item) for item in data if isinstance(item, dict)]


def _calculate_chunk_size(text: str) -> int:
    """Derive the optimal chunk size from the actual content density.

    Samples the first 20 data rows, estimates output tokens per row, and
    calculates how many rows safely fit within _TARGET_OUTPUT_TOKENS.
    Result is clamped to [10, 150].

    Note: uses compressed line length (collapse runs of spaces) to avoid
    being misled by pandas to_string() column-alignment padding.
    """
    import re

    lines = text.splitlines()
    data_lines = [l for l in lines[1:] if l.strip()]  # skip header + blanks
    if not data_lines:
        return CHUNK_SIZE

    sample = data_lines[:20]
    # Collapse consecutive whitespace → single space to get real content length
    compressed = [re.sub(r" {2,}", " ", l).strip() for l in sample]
    avg_chars = sum(len(l) for l in compressed) / len(compressed)

    # Estimate output tokens: JSON wraps each row with field names + structure
    output_tokens_per_row = (avg_chars * _JSON_OVERHEAD) / _CHARS_PER_TOKEN

    if output_tokens_per_row <= 0:
        return CHUNK_SIZE

    size = int(_TARGET_OUTPUT_TOKENS / output_tokens_per_row)
    return max(10, min(150, size))


def _split_table_into_chunks(text: str, chunk_size: int | None = None) -> list[str]:
    """Split a plain-text table into chunks, repeating header in each.

    If chunk_size is None, it is calculated dynamically from content density.

    Handles multi-line cells: pandas to_string() wraps long values across lines.
    A continuation line (no leading column alignment) is merged back into the
    previous data row before splitting to avoid sending broken rows to Claude.
    """
    import re

    effective_size = chunk_size if chunk_size is not None else _calculate_chunk_size(text)
    lines = text.splitlines()
    if not lines:
        return [text]

    header = lines[0]
    raw_data = lines[1:]

    # Detect column start positions from header to identify continuation lines.
    # A continuation line starts with whitespace where the first column would be.
    col_positions = [m.start() for m in re.finditer(r"\S", header)]
    first_col_start = col_positions[0] if col_positions else 0

    merged: list[str] = []
    for line in raw_data:
        if not line.strip():
            continue
        # If line starts before first column position → it's a continuation
        if merged and line and not line[first_col_start].strip():
            merged[-1] = merged[-1].rstrip() + " " + line.strip()
        else:
            merged.append(line)

    if len(merged) <= effective_size:
        return [header + "\n" + "\n".join(merged)]

    data_lines = merged
    chunks = []
    for i in range(0, len(data_lines), effective_size):
        block = [header] + data_lines[i : i + effective_size]
        chunks.append("\n".join(block))
    return chunks


def extract_line_items(
    sanitized_text: str,
    column_hints: str = "",
    api_key: str | None = None,
    call_fn=None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Extract line items. Uses call_fn(user_content, system_prompt, key) for API calls.

    Returns (items, usage) where usage = {"input_tokens": int, "output_tokens": int}.
    call_fn must return (text, input_tokens, output_tokens).
    If call_fn is None, auto-detects provider from key prefix.
    """
    key = api_key or os.getenv("ANTHROPIC_API_KEY") or ""
    if not key:
        raise RuntimeError("Kein API-Key gefunden. Bitte ANTHROPIC_API_KEY in .env setzen.")

    if call_fn is None:
        if key.startswith("sk-or-"):
            from offerten_converter.infrastructure.ai_extractors.openrouter_extractor import (
                call_openrouter,
            )
            call_fn = call_openrouter
        else:
            from offerten_converter.infrastructure.ai_extractors.anthropic_extractor import (
                call_anthropic,
            )
            call_fn = call_anthropic

    base_content = sanitized_text
    if column_hints:
        base_content = f"[Column hints: {column_hints}]\n\n{sanitized_text}"

    chunks = _split_table_into_chunks(base_content)
    logger.info("Sending %d chunk(s) (total %d chars).", len(chunks), len(base_content))

    all_items: list[dict] = []
    total_input = 0
    total_output = 0

    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            chunk = f"[Part {i+1} of {len(chunks)}]\n{chunk}"
        result = call_fn(chunk, SYSTEM_PROMPT, key)
        # Support both old (str) and new (tuple) return format
        if isinstance(result, tuple):
            raw, in_tok, out_tok = result
            total_input += in_tok
            total_output += out_tok
        else:
            raw = result
        items = _parse_response(raw)
        all_items.extend(items)
        logger.info("Chunk %d: extracted %d items.", i + 1, len(items))

    logger.info("Total extracted: %d line items.", len(all_items))
    usage = {"input_tokens": total_input, "output_tokens": total_output}
    return all_items, usage
