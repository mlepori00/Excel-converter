"""Smoke-test all offer skeletons through the no-AI (heuristic) pipeline.

For each demo file: read -> local extraction -> product rows -> price one row -> export.
Pure heuristic path, no Anthropic API calls. Reports per file what worked.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from offerten_converter.api.mappers import dataframe_to_product_rows  # noqa: E402
from offerten_converter.application.calculate_prices import enrich_dataframe  # noqa: E402
from offerten_converter.application.export_quotation import export_to_excel  # noqa: E402
from offerten_converter.domain.pricing import DEFAULT_RATES  # noqa: E402
from offerten_converter.infrastructure.excel_reader import read_offer_file  # noqa: E402
from offerten_converter.infrastructure.excel_writer import build_excel  # noqa: E402

# Mirror the route's _build_local_extraction so we test the real heuristic.
from offerten_converter.api.routes import _build_local_extraction, _enforce_import_truth  # noqa: E402

DEMO_DIR = Path(__file__).resolve().parent.parent / ".tmp_gerueste"


def _short(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}".replace("\n", " ")[:200]


def test_one(path: Path) -> dict:
    out: dict = {"file": path.name, "size_kb": round(path.stat().st_size / 1024)}
    file_bytes = path.read_bytes()
    try:
        result = read_offer_file(file_bytes, path.name)
    except Exception as exc:
        out["read"] = f"FAIL {_short(exc)}"
        return out

    hints = result.metadata_hints
    out["read"] = f"OK {len(result.df)}r x {len(result.df.columns)}c"
    out["layout"] = hints.get("layout_type")
    out["currency"] = hints.get("detected_currency")
    out["unpivot"] = result.was_unpivoted
    mapping = hints.get("column_mapping", {})
    out["mapped"] = ",".join(sorted(mapping.keys())) if mapping else "(none)"

    # Diagnose the three gating conditions of _build_local_extraction.
    from offerten_converter.api.routes import _has_values
    src = result.df
    def _hv(cols):
        return [c for c in cols if c in src.columns and _has_values(src[c])]
    out["_identity"] = _hv(["product_name", "sku", "ean"])
    out["_price"] = _hv(["unit_price"])
    out["_variant"] = _hv(["size", "color", "available_qty"])

    # Heuristic local extraction (no AI)
    try:
        local = _build_local_extraction(result)
    except Exception as exc:
        out["local"] = f"FAIL {_short(exc)}"
        return out
    if local is None:
        out["local"] = "NONE (needs AI button)"
        return out
    local = _enforce_import_truth(local, result.df)
    out["local"] = f"OK {len(local)} products"

    # To product rows
    try:
        rows = dataframe_to_product_rows(local)
        out["rows"] = f"OK {len(rows)}"
    except Exception as exc:
        out["rows"] = f"FAIL {_short(exc)}"
        return out

    # Price + export the first 5 rows to prove the rest of the pipeline.
    try:
        sample = local.head(5).copy()
        enriched = enrich_dataframe(sample, 20.0, "CHF", dict(DEFAULT_RATES))
        xls = export_to_excel(
            enriched, "TestLieferant", "AMP Sport GmbH", "CHF", 30, build_fn=build_excel
        )
        out["export"] = f"OK {round(len(xls)/1024)}kb xlsx"
    except Exception as exc:
        out["export"] = f"FAIL {_short(exc)}"
        out["_trace"] = traceback.format_exc()
    return out


def main() -> None:
    files = sorted(DEMO_DIR.glob("*.xlsx"), key=lambda p: int(p.stem))
    results = [test_one(f) for f in files]

    print("\n=== OFFERTEN-GERÜSTE: No-AI Pipeline Test ===\n")
    for r in results:
        ok = all(
            not str(v).startswith("FAIL") for k, v in r.items() if k != "_trace"
        )
        flag = "[OK  ]" if (ok and "OK" in str(r.get("export", ""))) else (
            "[->AI]" if "NONE" in str(r.get("local", "")) else "[FAIL]"
        )
        print(f"{flag} {r['file']} ({r['size_kb']} KB)")
        print(f"    read:    {r.get('read')}")
        print(f"    layout:  {r.get('layout')}  currency={r.get('currency')}  unpivot={r.get('unpivot')}")
        print(f"    mapped:  {r.get('mapped')}")
        if "NONE" in str(r.get("local", "")):
            print(f"    gate:    identity={r.get('_identity')} price={r.get('_price')} variant={r.get('_variant')}")
        print(f"    local:   {r.get('local')}")
        if "rows" in r:
            print(f"    rows:    {r.get('rows')}")
        if "export" in r:
            print(f"    export:  {r.get('export')}")
        if "_trace" in r:
            print("    --- trace ---")
            for line in r["_trace"].splitlines()[-6:]:
                print(f"    {line}")
        print()

    # Summary
    full = sum(1 for r in results if "OK" in str(r.get("export", "")))
    needs_ai = sum(1 for r in results if "NONE" in str(r.get("local", "")))
    failed = len(results) - full - needs_ai
    print(f"--- Zusammenfassung: {full}/{len(results)} komplett heuristisch, "
          f"{needs_ai} brauchen KI-Button, {failed} fehlerhaft ---")


if __name__ == "__main__":
    main()
