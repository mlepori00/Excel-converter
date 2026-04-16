"""Tab 1: Konvertieren – Upload → Sanitize → Extract → Price → Export."""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from offerten_converter.application.calculate_prices import enrich_dataframe
from offerten_converter.application.export_quotation import export_to_excel
from offerten_converter.application.extract_products import extract_line_items
from offerten_converter.application.manage_profiles import profile_to_hints
from offerten_converter.application.sanitize_data import sanitize_dataframe
from offerten_converter.infrastructure.file_profile_repo import FileProfileRepository
from offerten_converter.ui.state import clear_extraction, get_settings

logger = logging.getLogger(__name__)

_repo = FileProfileRepository()

# Pricing per 1M tokens (USD) – Claude Opus 4.5 (real rates from API dashboard)
_PRICE_INPUT_PER_M = 15.0   # $15 / 1M input tokens
_PRICE_OUTPUT_PER_M = 75.0  # $75 / 1M output tokens
# 1 token ≈ 4 characters for mixed text/numbers
_CHARS_PER_TOKEN = 4
# Each extracted row produces ~80 output tokens (10 JSON fields × ~8 tokens each)
_OUTPUT_TOKENS_PER_ROW = 80

# Size detection: shoe sizes (numeric) and clothing sizes (text)
_SHOE_SIZE_RANGE = (20, 55)
_TEXT_SIZES = frozenset([
    "XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL",
    "2XL", "3XL", "4XL", "5XL", "ONE SIZE",
])


@dataclass
class ReadResult:
    """Result of reading and preprocessing an uploaded file."""
    df: pd.DataFrame
    metadata_hints: dict[str, Any] = field(default_factory=dict)
    was_unpivoted: bool = False
    unpivot_info: str = ""


def _estimate_api_cost(text: str, n_chunks: int) -> None:
    """Show estimated API cost before extraction starts.

    Uses the same chunk-size logic as the actual extraction so the estimate
    stays accurate regardless of file size or content density.
    """
    from offerten_converter.application.extract_products import (
        SYSTEM_PROMPT,
        _calculate_chunk_size,
    )

    system_tokens = len(SYSTEM_PROMPT) // _CHARS_PER_TOKEN
    content_tokens = len(text) // _CHARS_PER_TOKEN
    chunk_content_tokens = content_tokens // max(n_chunks, 1)

    # Input: each chunk sends system prompt + its slice of the content
    total_input = (system_tokens + chunk_content_tokens) * n_chunks

    # Output: use compressed line length (same as chunker) to avoid padding inflation
    import re
    lines = text.splitlines()
    data_lines = [l for l in lines[1:] if l.strip()]
    n_rows = len(data_lines)
    sample = data_lines[:20]
    compressed = [re.sub(r" {2,}", " ", l).strip() for l in sample]
    avg_chars = sum(len(l) for l in compressed) / max(len(compressed), 1)
    output_tokens_per_row = (avg_chars * 3.0) / _CHARS_PER_TOKEN
    total_output = int(n_rows * output_tokens_per_row)

    cost_in = total_input / 1_000_000 * _PRICE_INPUT_PER_M
    cost_out = total_output / 1_000_000 * _PRICE_OUTPUT_PER_M
    cost_usd = cost_in + cost_out
    cost_chf = cost_usd * 0.89  # approximate USD → CHF

    st.info(f"Geschätzte Kosten für diese Extraktion: **ca. CHF {cost_chf:.3f}**")


def _detect_header_row(df_raw: pd.DataFrame, max_scan: int = 50) -> int:
    """Find the best header row – prefers rows with many string values."""
    n_cols = len(df_raw.columns)
    min_fill = max(3, int(n_cols * 0.75))
    for i in range(min(len(df_raw), max_scan)):
        row = df_raw.iloc[i]
        non_null = [
            v for v in row
            if v is not None and not (isinstance(v, float) and pd.isna(v))
        ]
        if len(non_null) < min_fill:
            continue
        str_vals = [v for v in non_null if isinstance(v, str) and str(v).strip()]
        if len(str_vals) / len(non_null) >= 0.6:
            return i
    return 0


def _unmerge_cells(file_bytes: bytes, sheet_name: str | None = None) -> bytes:
    """Load xlsx with openpyxl, unmerge all cells (fill with top-left value), return bytes."""
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes))
    ws = wb[sheet_name] if sheet_name else wb.active

    if not ws.merged_cells.ranges:
        return file_bytes  # nothing to do

    for merge_range in list(ws.merged_cells.ranges):
        min_col, min_row, max_col, max_row = merge_range.bounds
        top_left_value = ws.cell(min_row, min_col).value
        ws.unmerge_cells(str(merge_range))
        for r in range(min_row, max_row + 1):
            for c in range(min_col, max_col + 1):
                ws.cell(r, c).value = top_left_value

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    logger.info("Unmerged %d cell ranges.", len(list(ws.merged_cells.ranges)))
    return buf.read()


def _extract_metadata_hints(df_raw: pd.DataFrame, header_row: int) -> dict[str, Any]:
    """Scan rows above the header for currency info and other metadata."""
    hints: dict[str, Any] = {}

    for i in range(header_row):
        row_text = " ".join(
            str(v) for v in df_raw.iloc[i] if v is not None and str(v).strip()
        ).upper()

        # Detect currency hints like "Currency = USD" or "Währung: EUR"
        import re
        curr_match = re.search(
            r"(?:CURRENCY|WÄHRUNG|WAEHRUNG)\s*[=:]\s*(USD|EUR|CHF|GBP)", row_text,
        )
        if curr_match:
            hints["detected_currency"] = curr_match.group(1)

    return hints


def _detect_size_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Detect if columns represent sizes (shoe sizes 20-55 or text S/M/L/XL).

    Returns (size_columns, other_columns). Empty size_columns if no pattern found.
    """
    size_cols: list[str] = []
    other_cols: list[str] = []

    # Check for numeric shoe size headers (35, 36, 37, ...)
    for col in df.columns:
        try:
            val = float(col)
            if _SHOE_SIZE_RANGE[0] <= val <= _SHOE_SIZE_RANGE[1]:
                size_cols.append(col)
            else:
                other_cols.append(col)
        except (ValueError, TypeError):
            other_cols.append(col)

    if len(size_cols) >= 3:
        return size_cols, other_cols

    # Check for text clothing size headers
    size_cols = []
    other_cols = []
    for col in df.columns:
        if str(col).upper().strip() in _TEXT_SIZES:
            size_cols.append(col)
        else:
            other_cols.append(col)

    if len(size_cols) >= 3:
        return size_cols, other_cols

    return [], list(df.columns)


def _unpivot_sizes(
    df: pd.DataFrame, size_cols: list[str], other_cols: list[str],
) -> pd.DataFrame:
    """Melt size columns into rows: each (product, size) becomes one row."""
    melted = df.melt(
        id_vars=other_cols,
        value_vars=size_cols,
        var_name="_size_from_col",
        value_name="_qty_from_col",
    )
    # Convert qty to numeric, drop rows with 0 or null qty
    melted["_qty_from_col"] = pd.to_numeric(melted["_qty_from_col"], errors="coerce")
    melted = melted[melted["_qty_from_col"].notna() & (melted["_qty_from_col"] > 0)]
    melted = melted.reset_index(drop=True)
    return melted


def _read_uploaded_file(uploaded_file) -> ReadResult:
    """Read and preprocess an uploaded file.

    Handles: merged cells, size-column unpivot, metadata extraction.
    """
    name = uploaded_file.name.lower()
    raw_bytes = uploaded_file.read()

    if name.endswith(".csv"):
        for sep in (",", ";", "\t"):
            try:
                df = pd.read_csv(io.BytesIO(raw_bytes), sep=sep, dtype=str)
                if len(df.columns) > 1:
                    return ReadResult(df=df)
            except Exception:
                continue
        return ReadResult(df=pd.read_csv(io.BytesIO(raw_bytes), dtype=str))

    try:
        # Step 1: Unmerge cells if xlsx
        if name.endswith(".xlsx"):
            import openpyxl
            wb_check = openpyxl.load_workbook(io.BytesIO(raw_bytes))
            ws_check = wb_check.active
            has_merged = bool(ws_check.merged_cells.ranges)
            sheet_names = wb_check.sheetnames
            wb_check.close()
        else:
            has_merged = False
            xl_tmp = pd.ExcelFile(io.BytesIO(raw_bytes))
            sheet_names = xl_tmp.sheet_names

        # Sheet selection
        if len(sheet_names) > 1:
            chosen = st.selectbox(
                "Mehrere Tabellenblätter gefunden – bitte wählen:",
                sheet_names,
                key="sheet_select",
            )
        else:
            chosen = sheet_names[0]

        # Unmerge if needed
        if has_merged:
            processed_bytes = _unmerge_cells(raw_bytes, chosen)
            st.info("📐 Zusammengeführte Zellen wurden automatisch aufgelöst.")
        else:
            processed_bytes = raw_bytes

        buf = io.BytesIO(processed_bytes)
        xl = pd.ExcelFile(buf)

        df_raw = xl.parse(chosen, header=None)
        header_row = _detect_header_row(df_raw)

        # Extract metadata from rows above header
        metadata_hints = _extract_metadata_hints(df_raw, header_row)

        if header_row > 0:
            st.info(
                f"Header in Zeile {header_row + 1} erkannt "
                f"({header_row} Metadaten-Zeile(n) übersprungen)."
            )

        df = xl.parse(chosen, header=header_row, dtype=str)
        df = df.dropna(how="all").reset_index(drop=True)
        df = df[[
            c for c in df.columns
            if not (str(c).startswith("Unnamed:") and df[c].isna().all())
        ]]

        # Step 2: Detect and unpivot size columns
        size_cols, other_cols = _detect_size_columns(df)
        was_unpivoted = False
        unpivot_info = ""

        if size_cols:
            original_rows = len(df)
            df = _unpivot_sizes(df, size_cols, other_cols)
            was_unpivoted = True
            unpivot_info = (
                f"Grössen-Spalten erkannt ({len(size_cols)} Grössen: "
                f"{size_cols[0]}–{size_cols[-1]}). "
                f"{original_rows} Zeilen → {len(df)} Varianten-Zeilen (Unpivot)."
            )
            st.success(f"📊 {unpivot_info}")

        if metadata_hints.get("detected_currency"):
            st.info(
                f"💱 Währung aus Metadaten erkannt: "
                f"**{metadata_hints['detected_currency']}**"
            )

        return ReadResult(
            df=df,
            metadata_hints=metadata_hints,
            was_unpivoted=was_unpivoted,
            unpivot_info=unpivot_info,
        )

    except Exception as exc:
        st.error(f"Fehler beim Lesen der Excel-Datei: {exc}")
        st.stop()


def render():
    """Render the Konvertieren tab."""
    settings = get_settings()

    with st.sidebar:
        st.header("Preiseinstellungen")
        margin_pct = st.number_input(
            "Ziel-Marge %",
            min_value=0.0, max_value=99.0,
            value=settings["default_margin"],
            step=0.5, format="%.1f",
        )
        target_currency = st.selectbox(
            "Zielwährung",
            ["CHF", "EUR", "USD"],
            index=["CHF", "EUR", "USD"].index(settings["default_currency"]),
        )
        st.divider()
        st.caption(f"Standardmarge: {settings['default_margin']}%")

    # Step 1: Supplier name
    st.subheader("1. Lieferant")
    col_sup, col_prof = st.columns([2, 2])

    with col_sup:
        supplier_name = st.text_input(
            "Lieferantenname (manuell eingeben – wird nicht an API gesendet)",
            value=st.session_state["supplier_name"],
            placeholder="z.B. Sport Muster GmbH",
        )
        st.session_state["supplier_name"] = supplier_name

    with col_prof:
        profiles = _repo.list_profiles()
        if profiles:
            load_choice = st.selectbox(
                "Profil laden (optional)",
                ["– kein Profil –"] + profiles,
                key="profile_load_select",
            )
        else:
            load_choice = "– kein Profil –"
            st.info("Noch keine Lieferantenprofile gespeichert.")

    loaded_profile = None
    if load_choice != "– kein Profil –":
        loaded_profile = _repo.load(load_choice)
        if loaded_profile:
            # Use profile name as supplier name if not manually entered
            if not supplier_name:
                supplier_name = loaded_profile["name"]
                st.session_state["supplier_name"] = supplier_name
            st.success(
                f"Profil geladen: {loaded_profile['name']} | "
                f"Währung: {loaded_profile.get('typical_currency', '?')} | "
                f"Rabatt: {loaded_profile.get('typical_discount', 0)}%"
            )

    # Step 2: File upload
    st.subheader("2. Datei hochladen")
    uploaded = st.file_uploader(
        "Lieferanten-Offerte hochladen (.xlsx, .xls, .csv)",
        type=["xlsx", "xls", "csv"],
        key="file_uploader",
    )

    if uploaded is None:
        clear_extraction()
        st.info("Bitte eine Datei hochladen, um fortzufahren.")
        return

    fingerprint = f"{uploaded.name}::{uploaded.size}"
    if st.session_state["_file_fingerprint"] != fingerprint:
        clear_extraction()
        st.session_state["_file_fingerprint"] = fingerprint

    result = _read_uploaded_file(uploaded)
    df_raw = result.df

    info_parts = [f"{len(df_raw)} Zeilen", f"{len(df_raw.columns)} Spalten"]
    if result.was_unpivoted:
        info_parts.append("(nach Unpivot)")
    st.caption(f"Datei gelesen: {', '.join(info_parts)}")

    # Step 3: Sanitize
    st.subheader("3. Datenschutz-Bereinigung")
    df_clean, sanitize_log = sanitize_dataframe(df_raw)
    st.session_state["sanitize_log"] = sanitize_log

    if sanitize_log:
        cols_removed = [e for e in sanitize_log if e.startswith("Spalte")]
        cells_scrubbed = [e for e in sanitize_log if e.startswith("Zelle")]
        label = (
            f"🛡️ {len(cols_removed)} Spalte(n) entfernt"
            + (f", {len(cells_scrubbed)} Zelle(n) geschwärzt" if cells_scrubbed else "")
        )
        with st.expander(label, expanded=True):
            if cols_removed:
                st.markdown("**Entfernte Spalten:**")
                for entry in cols_removed:
                    st.markdown(f"- {entry}")
            if cells_scrubbed:
                st.markdown("**Geschwärzte Zellinhalte:**")
                for entry in cells_scrubbed:
                    st.markdown(f"- {entry}")
    else:
        st.success("Keine sensiblen Felder gefunden – alle Spalten bleiben erhalten.")

    with st.expander("Bereinigtes Daten-Preview (wird an API gesendet)", expanded=False):
        st.dataframe(df_clean.head(20), use_container_width=True)

    sanitized_text = df_clean.to_string(index=False)

    # Step 4: Extract
    st.subheader("4. KI-Extraktion")

    from offerten_converter.application.extract_products import _split_table_into_chunks
    n_chunks = len(_split_table_into_chunks(sanitized_text))
    _estimate_api_cost(sanitized_text, n_chunks)

    col_btn, col_hint = st.columns([1, 3])
    with col_btn:
        extract_btn = st.button("Extraktion starten", type="primary")
    with col_hint:
        st.caption(
            "Claude analysiert die bereinigte Produkttabelle "
            "und extrahiert alle Positionen."
        )

    if extract_btn:
        st.session_state["extracted_df"] = None
        st.session_state["raw_api_response"] = None
        st.session_state["extraction_error"] = None
        st.session_state["api_usage"] = None

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            st.error("ANTHROPIC_API_KEY nicht gefunden. Bitte in der .env-Datei setzen.")
            return

        hints = profile_to_hints(loaded_profile) if loaded_profile else ""

        # Add auto-detected metadata hints
        extra_hints = []
        if result.was_unpivoted:
            extra_hints.append(
                "Data was unpivoted: '_size_from_col' contains the size, "
                "'_qty_from_col' contains the quantity per size. "
                "Use _size_from_col as 'size' and _qty_from_col as 'ordered_qty'."
            )
        if result.metadata_hints.get("detected_currency"):
            extra_hints.append(
                f"Detected currency: {result.metadata_hints['detected_currency']}"
            )
        if extra_hints:
            hints = (hints + " | " if hints else "") + " | ".join(extra_hints)

        with st.spinner("Claude extrahiert Positionen …"):
            try:
                items, usage = extract_line_items(sanitized_text, hints, api_key)
                df_extracted = pd.DataFrame(items)

                # If the file contains a mix of ordered (qty > 0) and unordered
                # (qty == 0) lines, automatically drop the zero-qty lines.
                # This handles order files that include full catalog rows alongside
                # the actual order positions.
                if "ordered_qty" in df_extracted.columns:
                    qty_col = pd.to_numeric(df_extracted["ordered_qty"], errors="coerce")
                    has_ordered = (qty_col > 0).any()
                    has_zero = (qty_col == 0).any()
                    if has_ordered and has_zero:
                        n_before = len(df_extracted)
                        df_extracted = df_extracted[qty_col > 0].reset_index(drop=True)
                        n_dropped = n_before - len(df_extracted)
                        st.info(
                            f"ℹ️ {n_dropped} Positionen mit Menge = 0 wurden automatisch "
                            f"entfernt (Katalogpositionen ohne Bestellung)."
                        )

                st.session_state["extracted_df"] = df_extracted
                st.session_state["api_usage"] = usage
                st.success(f"{len(df_extracted)} Positionen extrahiert.")
            except ValueError as exc:
                st.session_state["extraction_error"] = str(exc)
            except RuntimeError as exc:
                st.error(f"API-Fehler: {exc}")
                return

    if st.session_state.get("extraction_error"):
        st.error("Ungültige JSON-Antwort von Claude:")
        st.code(st.session_state["extraction_error"])
        st.warning("Bitte Extraktion erneut versuchen oder die Datei prüfen.")
        return

    if st.session_state["extracted_df"] is None:
        return

    # Step 5: Review & edit
    st.subheader("5. Extraktion prüfen & bearbeiten")

    if supplier_name:
        with st.expander("Als Lieferantenprofil speichern"):
            col_c, col_d, col_h = st.columns([1, 1, 2])
            with col_c:
                prof_currency = st.text_input("Typische Währung", value="EUR", key="prof_cur")
            with col_d:
                prof_discount = st.number_input(
                    "Typischer Rabatt %", 0.0, 100.0, 0.0, 0.5, key="prof_disc",
                )
            with col_h:
                prof_hints = st.text_area(
                    "Spalten-Hinweise (optional)",
                    placeholder='z.B. "Artikelnr=sku, Preis=unit_price"',
                    key="prof_hints",
                )
            if st.button("Profil speichern"):
                _repo.save(supplier_name, prof_currency, prof_discount, prof_hints)
                st.success(f"Profil '{supplier_name}' gespeichert.")

    df_edit = st.session_state["extracted_df"].copy()
    if "vk_target" not in df_edit.columns:
        df_edit["vk_target"] = None
    if "ordered_qty" not in df_edit.columns:
        df_edit["ordered_qty"] = None

    # Serialize extra_fields dict → readable string for display
    if "extra_fields" in df_edit.columns:
        df_edit["extra_fields_display"] = df_edit["extra_fields"].apply(
            lambda v: " | ".join(f"{k}: {val}" for k, val in v.items() if val is not None)
            if isinstance(v, dict) else ""
        )
    else:
        df_edit["extra_fields_display"] = ""

    column_config = {
        "sku": st.column_config.TextColumn("SKU"),
        "ean": st.column_config.TextColumn("EAN"),
        "product_name": st.column_config.TextColumn("Bezeichnung", width="large"),
        "size": st.column_config.TextColumn("Grösse"),
        "color": st.column_config.TextColumn("Farbe"),
        "category": st.column_config.TextColumn("Kategorie"),
        "unit_price": st.column_config.NumberColumn("EK/Stk (orig.)", format="%.4f"),
        "currency": st.column_config.TextColumn("Währung"),
        "ordered_qty": st.column_config.NumberColumn("Bestellt", format="%d"),
        "min_qty": st.column_config.NumberColumn("Min. Menge", format="%d"),
        "discount_pct": st.column_config.NumberColumn("Rabatt %", format="%.2f"),
        "notes": st.column_config.TextColumn("Notizen", width="medium"),
        "extra_fields_display": st.column_config.TextColumn(
            "Zusatzinfos", width="large", disabled=True,
        ),
        "vk_target": st.column_config.NumberColumn("VK manuell (leer=auto)", format="%.4f"),
    }

    edited_df = st.data_editor(
        df_edit, column_config=column_config,
        num_rows="dynamic", use_container_width=True, key="data_editor",
    )
    st.session_state["extracted_df"] = edited_df

    # Step 6: Pricing preview
    st.subheader("6. Kalkulation")
    rates = settings["rates"]
    enriched = enrich_dataframe(edited_df, margin_pct, target_currency, rates)
    st.session_state["enriched_df"] = enriched

    display_cols = [
        "product_name", "sku", "currency", "qty",
        "ek_unit_target", "ek_target", "margin_actual",
        "vk_unit_target", "vk_target",
    ]
    display_cols = [c for c in display_cols if c in enriched.columns]
    display_df = enriched[display_cols].copy()

    def _color_margin(val):
        if pd.isna(val):
            return "color: gray"
        if val >= 20:
            return "color: green; font-weight:bold"
        if val >= 10:
            return "color: orange; font-weight:bold"
        return "color: red; font-weight:bold"

    styled = display_df.style.applymap(_color_margin, subset=["margin_actual"])
    st.dataframe(styled, use_container_width=True)

    col_s1, col_s2, col_s3 = st.columns(3)
    ek_total = enriched["ek_target"].sum(skipna=True)
    vk_total = enriched["vk_target"].sum(skipna=True)
    avg_marg = enriched["margin_actual"].mean(skipna=True)
    col_s1.metric(f"Total EK ({target_currency})", f"{ek_total:,.2f}")
    col_s2.metric(f"Total VK ({target_currency})", f"{vk_total:,.2f}")
    col_s3.metric("Ø Marge %", f"{avg_marg:.1f}%" if not pd.isna(avg_marg) else "–")

    # Step 7: Export
    st.subheader("7. Export")
    created_by = settings.get("company_name", "")
    valid_days = settings.get("valid_days", 30)

    # Use profile name as fallback for supplier name
    effective_supplier = supplier_name
    if not effective_supplier and loaded_profile:
        effective_supplier = loaded_profile.get("name", "")

    if not effective_supplier:
        st.warning("Bitte zuerst den Lieferantennamen eingeben (Schritt 1).")
    elif enriched.empty:
        st.warning("Keine Positionen zum Exportieren vorhanden.")
    else:
        try:
            excel_bytes = export_to_excel(
                enriched, effective_supplier, created_by, target_currency, valid_days,
            )
            today_str = date.today().strftime("%Y%m%d")
            filename = f"Offerte_{effective_supplier.replace(' ', '_')}_{today_str}.xlsx"
            st.download_button(
                label="Export Offerte (.xlsx)",
                data=excel_bytes, file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
        except Exception as exc:
            st.error(f"Export-Fehler: {exc}")
